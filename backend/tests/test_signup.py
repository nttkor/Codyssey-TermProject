"""
AskMate 회원가입 기능 및 보안 통합 테스트 (Sign-up Integration & Security Tests)

[파일 개요]
본 모듈은 회원가입 API(`/api/signup`)의 비즈니스 로직, 입력값 유효성 검사 경계값,
Argon2id 무작위 솔트 암호화, 대소문자 무시(Case-insensitive) 중복 가입 방지,
동시성(Concurrency) 제어, 데이터베이스 롤백 및 감사 로그의 민감정보 비노출 여부를 검증합니다.

[주요 검증 항목]
1. 해싱 및 보안 규격 (`test_signup_saves_user_with_random_salt`):
   - 비밀번호가 고유한 솔트와 함께 `$argon2id$` 형식으로 안전하게 해싱되어 저장되는지 확인.
   - 가입 성공 응답이나 애플리케이션 로그에 비밀번호 평문이나 해시값이 노출되지 않는지 확인.
   - 회원가입 직후 불필요한 세션 쿠키(`set-cookie`)가 발급되지 않는지 확인.
2. 입력 경계값 및 422 에러 마스킹 (`test_password_boundaries`, `test_invalid_input_is_not_saved_or_echoed`):
   - 비밀번호 최소(8자), 최대(128자) 및 유니코드(한글) 허용 검증.
   - 잘못된 형식(길이 미달, 금지 문자 등) 입력 시 422 상태 코드가 반환되고 입력값이 응답에 에코되지 않는지 검증.
3. 중복 가입 및 동시성 방어 (`test_duplicate_username_is_case_insensitive`, `test_concurrent_signup_creates_one_user`):
   - 대소문자만 다른 아이디(`charles` vs ` CHARLES `) 가입 시 409 Conflict 처리.
   - 멀티스레드 환경(`ThreadPoolExecutor`, `Barrier`)에서 동일 아이디로 동시 가입 시 단 1건만 성공(201)하고 나머지는 차단(409)되는지 확인.
4. 트랜잭션 롤백 및 데이터 영속성 (`test_duplicate_rolls_back_...`, `test_users_survive_app_restart`):
   - 예외 발생 시 트랜잭션이 깨끗하게 롤백되어 다음 요청이 정상 처리되는지 및 서버 재기동 후에도 데이터가 유지되는지 확인.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from sqlite3 import OperationalError as SQLiteOperationalError
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

# 테스트 공통 비밀번호 상수
PASSWORD = "  a long password phrase  "


def read_users():
    """데이터베이스에서 모든 사용자 엔티티를 ID 오름차순으로 조회하는 헬퍼 함수."""
    from app.db_connect import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        return db.scalars(select(User).order_by(User.id)).all()


def test_signup_saves_user_with_random_salt(client, caplog):
    """회원가입 시 사용자명이 정규화되고 고유한 무작위 솔트로 비밀번호가 해싱되는지 검증합니다."""
    from app.security import password_hasher

    caplog.set_level("INFO")
    response = client.post("/api/signup", json={"username": " Charles_1 ", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "charles_1"}
    assert "set-cookie" not in response.headers  # 자동 로그인 방지

    # 동일한 비밀번호로 두 번째 사용자 가입 (서로 다른 솔트 생성 확인)
    assert client.post("/api/signup", json={"username": "another", "password": PASSWORD}).status_code == 201
    first, second = read_users()
    assert first.password_hash.startswith("$argon2id$")
    assert first.password_hash != second.password_hash  # 솔트 무작위성 검증
    assert password_hasher.verify(PASSWORD, first.password_hash)
    assert not password_hasher.verify(PASSWORD.strip(), first.password_hash)  # 비밀번호 공백 보존 확인
    assert abs((datetime.now(UTC) - first.created_at.replace(tzinfo=UTC)).total_seconds()) < 60
    assert "db_save_success operation=signup" in caplog.text
    assert PASSWORD not in caplog.text  # 로그 내 비밀번호 평문 노출 방지 확인
    assert first.password_hash not in caplog.text  # 로그 내 해시 노출 방지 확인


@pytest.mark.parametrize("password", ["p" * 8, "p" * 128, "긴 비밀번호 문장입니다 반갑습니다"])
def test_password_boundaries(client, password):
    """비밀번호 최소 길이(8자), 최대 길이(128자) 및 다국어 유니코드 입력이 허용되는지 검증합니다."""
    response = client.post("/api/signup", json={"username": "valid_user", "password": password})
    assert response.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        {"password": PASSWORD},
        {"username": "valid_user"},
        {"username": "ab", "password": PASSWORD},
        {"username": "a" * 31, "password": PASSWORD},
        {"username": "   ", "password": PASSWORD},
        {"username": "has space", "password": PASSWORD},
        {"username": "invalid!", "password": PASSWORD},
        {"username": "valid_user", "password": "p" * 7},
        {"username": "valid_user", "password": "p" * 129},
        {"username": "valid_user", "password": 123456789012345},
        {"username": "valid_user", "password": {"secret": PASSWORD}},
        [PASSWORD],
    ],
)
def test_invalid_input_is_not_saved_or_echoed(client, payload):
    """유효하지 않은 요청 데이터는 422 상태 코드로 거부되며 입력값이 응답에 노출되지 않는지 검증합니다."""
    response = client.post("/api/signup", json=payload)
    assert response.status_code == 422
    assert PASSWORD not in response.text  # 평문 비밀번호 에코 방지 확인
    assert all(set(error) == {"type", "loc", "msg"} for error in response.json()["detail"])
    assert read_users() == []


def test_duplicate_username_is_case_insensitive(client):
    """대소문자만 다른 중복 사용자명 가입 시 409 Conflict가 반환되는지 검증합니다."""
    assert client.post("/api/signup", json={"username": "charles", "password": PASSWORD}).status_code == 201
    response = client.post("/api/signup", json={"username": " CHARLES ", "password": PASSWORD})
    assert response.status_code == 409
    assert response.json() == {"detail": "이미 사용 중인 사용자명입니다."}
    assert len(read_users()) == 1


def test_concurrent_signup_creates_one_user(client):
    """동일 아이디로 동시 요청(Race condition) 발생 시 단 1건만 생성되고 나머지는 409로 차단되는지 검증합니다."""
    barrier = Barrier(2)

    def signup():
        barrier.wait(timeout=10)
        return client.post("/api/signup", json={"username": "same_user", "password": PASSWORD}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [executor.submit(signup) for _ in range(2)]
        assert sorted(result.result(timeout=15) for result in results) == [201, 409]
    assert len(read_users()) == 1


def test_duplicate_rolls_back_and_session_can_be_reused(client):
    """중복 가입 예외 발생 시 트랜잭션이 정상 롤백되어 동일 세션에서 다음 가입이 성공하는지 검증합니다."""
    from app.account_db import create_user
    from app.db_connect import SessionLocal
    from app.security import hash_password

    password_hash = hash_password(PASSWORD)
    with SessionLocal() as db:
        create_user(db, "original", password_hash)
        with pytest.raises(IntegrityError):
            create_user(db, "original", password_hash)
        assert not db.in_transaction()
        create_user(db, "next_user", password_hash)
    assert len(read_users()) == 2


def test_non_unique_constraint_error_returns_500_without_hash(client, caplog):
    """예기치 않은 DB 제약조건 오류 발생 시 500 응답과 함께 비밀번호 해시가 은닉되는지 검증합니다."""
    from app.models.user import User

    def invalidate_username(session, flush_context, instances):
        for user in session.new:
            if isinstance(user, User):
                user.username = None

    event.listen(Session, "before_flush", invalidate_username)
    try:
        response = client.post("/api/signup", json={"username": "valid_user", "password": PASSWORD})
    finally:
        event.remove(Session, "before_flush", invalidate_username)

    assert response.status_code == 500
    assert response.json() == {"detail": "회원가입 정보를 저장하지 못했습니다."}
    assert read_users() == []
    assert "db_save_failure operation=signup" in caplog.text
    assert "SQL parameters hidden" in caplog.text
    assert "$argon2" not in caplog.text
    assert PASSWORD not in caplog.text


def test_commit_failure_rolls_back_and_next_signup_works(client):
    """DB 커밋 실패 시 자동 롤백된 후 다음 회원가입 요청이 정상적으로 처리되는지 검증합니다."""
    def fail_commit(session):
        raise OperationalError("COMMIT", {}, SQLiteOperationalError("test failure"))

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        response = client.post("/api/signup", json={"username": "valid_user", "password": PASSWORD})
    assert response.status_code == 500
    assert read_users() == []
    assert client.post("/api/signup", json={"username": "valid_user", "password": PASSWORD}).status_code == 201


def test_users_survive_app_restart(application, csrf_headers):
    """애플리케이션 재기동 후에도 회원 데이터가 SQLite 데이터베이스에 영구 보존되는지 검증합니다."""
    with TestClient(application, headers=csrf_headers) as client:
        response = client.post("/api/signup", json={"username": "persistent", "password": PASSWORD})
        assert response.status_code == 201
        user_id = response.json()["id"]
    with TestClient(application) as restarted:
        assert restarted.get("/health").json() == {"status": "ok"}
        assert any(user.id == user_id and user.username == "persistent" for user in read_users())


def test_existing_pages_and_chat_validation(client):
    """주요 웹 페이지 경로 응답 및 대화 엔드포인트의 기본 인증/검증 상태를 점검합니다."""
    for path in ["/health", "/docs", "/openapi.json", "/signup", "/static/css/style.css"]:
        assert client.get(path).status_code == 200
    assert client.post("/api/chat", json={"question": "hello"}).status_code == 401
    credentials = {"username": "chat_user", "password": PASSWORD}
    assert client.post("/api/signup", json=credentials).status_code == 201
    assert client.post("/api/login", json=credentials).status_code == 200
    # 인증·검증을 통과하면 AI 통신 단계까지 진입합니다. (테스트 설정의 주소는 해석되지 않아 502 발생)
    assert client.post("/api/chat", json={"question": "hello"}).status_code == 502
    assert client.post("/api/chat", json={"question": " "}).status_code == 422
