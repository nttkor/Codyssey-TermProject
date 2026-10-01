"""
AskMate 대화 기록 영구 저장 및 트랜잭션 롤백 테스트 (Chat Storage & Rollback Tests)

[파일 개요]
본 모듈은 AI 대화 완료 후 질문과 답변이 SQLite 데이터베이스(`chats` 테이블)에
정확하게 영구 저장되는지, 그리고 AI 호출 실패나 DB 오류 발생 시 원자적 롤백(Rollback)이
올바르게 수행되어 데이터 불일치나 미완성 레코드가 생성되지 않는지 철저히 검증합니다.

[주요 검증 항목]
1. 정상 저장 및 UTC 타임스탬프 (`test_chat_saves_question_answer_and_utc_time`):
   - 질문과 답변 원문(줄바꿈, 1000자 경계값)이 그대로 보존되어 저장되는지 확인.
   - 시간대 오프셋이 배제된 UTC 나이브 datetime으로 저장되는지 확인.
   - 로그에 질문 본문, 답변 본문, 비밀번호가 기록되지 않는지 확인.
2. 세션 기반 소유권 강제 (`test_chat_owner_comes_from_session`):
   - 요청 본문에 타인의 `user_id`를 전달하더라도 무시하고 세션 쿠키의 소유자 ID로만 저장되는지 확인.
3. 사전 거부 및 통신 실패 시 미저장 보장:
   - 401(비로그인), 403(CSRF 누락), 422(글자수 위반) 시 AI 미호출 및 DB 미저장 확인 (`test_rejected_request_...`).
   - AI 통신 장애(502), 타임아웃(504), 예기치 않은 런타임 오류 발생 시 DB에 일체 저장되지 않음을 확인.
4. 트랜잭션 무결성 및 외래키 제약조건 (`test_foreign_key_failure_...`, `test_commit_failure_...`):
   - 외래키 위반 시 즉각 롤백되어 세션이 재사용 가능한 상태를 유지하는지 확인.
   - DB commit 실패 시 세션이 롤백되고 다음 채팅 요청이 정상 처리되는지 확인.
5. 스키마 자동 확장 및 재기동 보존 (`test_existing_user_db_gets_chats_and_records_survive_restart`):
   - 기존 users 테이블만 존재하던 구버전 DB에 chats 테이블이 자동 추가되고 인덱스가 생성되는지 확인.
"""

from datetime import UTC, datetime
import os
from pathlib import Path
from sqlite3 import OperationalError as SQLiteOperationalError
import subprocess
import sys

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

# 테스트 공통 상수
PASSWORD = "a long password phrase"
ANSWER = "테스트 답변입니다.\n두 번째 줄도 그대로 저장합니다."


@pytest.fixture
def logged_in_user(client):
    """채팅 저장 테스트용 사용자를 생성하고 로그인하는 픽스처.

    Returns:
        dict: 생성된 사용자 정보 {"id": int, "username": str}
    """
    credentials = {"username": "chat_user", "password": PASSWORD}
    response = client.post("/api/signup", json=credentials)
    assert response.status_code == 201
    assert client.post("/api/login", json=credentials).status_code == 200
    return response.json()


@pytest.fixture
def ai_calls(monkeypatch):
    """AI 응답을 고정된 답변(ANSWER)으로 모킹하고 호출 인자를 수집하는 픽스처."""
    from app import llm_connect

    calls = []

    async def answer(question, history):
        calls.append((question, history))
        return ANSWER

    monkeypatch.setattr(llm_connect, "generate_answer", answer)
    return calls


def read_chats():
    """데이터베이스에 저장된 모든 대화 엔티티를 ID 오름차순으로 조회하는 헬퍼 함수."""
    from app.db_connect import SessionLocal
    from app.models.chat import Chat

    with SessionLocal() as db:
        return db.scalars(select(Chat).order_by(Chat.id)).all()


def test_chat_saves_question_answer_and_utc_time(client, logged_in_user, ai_calls, caplog):
    """질문, 답변, 소유자 ID, UTC 생성 시각이 데이터베이스에 정상적으로 저장되는지 검증합니다."""
    caplog.set_level("INFO")
    for question in ("  첫 질문입니다.\n다음 줄  ", "질" * 1000):
        response = client.post("/api/chat", json={"question": question})
        assert response.status_code == 200
        assert response.json() == {"answer": ANSWER}

    chats = read_chats()
    assert len(chats) == 2
    assert [chat.question for chat in chats] == ["첫 질문입니다.\n다음 줄", "질" * 1000]
    assert ai_calls == [
        (chats[0].question, []),
        (chats[1].question, [
            {"role": "user", "content": chats[0].question},
            {"role": "assistant", "content": ANSWER},
        ]),
    ]
    for chat in chats:
        assert chat.user_id == logged_in_user["id"]
        assert chat.answer == ANSWER
        assert chat.created_at.tzinfo is None  # 나이브 datetime 확인
        assert abs((datetime.now(UTC) - chat.created_at.replace(tzinfo=UTC)).total_seconds()) < 60
        assert f"db_save_success operation=chat user_id={chat.user_id} chat_id={chat.id}" in caplog.text
        assert chat.question not in caplog.text  # 질문 본문 로그 비노출 확인
    assert ANSWER not in caplog.text
    assert PASSWORD not in caplog.text


def test_chat_owner_comes_from_session(client, logged_in_user, ai_calls):
    """요청 본문의 변조된 user_id를 무시하고 세션 쿠키의 로그인 사용자 ID가 대화 소유자로 저장되는지 검증합니다."""
    other_credentials = {"username": "another_user", "password": PASSWORD}
    response = client.post("/api/signup", json=other_credentials)
    assert response.status_code == 201
    other_id = response.json()["id"]

    # 첫 번째 사용자가 다른 사용자의 ID를 본문에 실어 전송
    response = client.post("/api/chat", json={"question": "첫 사용자", "user_id": other_id})
    assert response.status_code == 200
    # 두 번째 사용자로 전환 로그인 후 첫 번째 사용자의 ID를 실어 전송
    assert client.post("/api/login", json=other_credentials).status_code == 200
    response = client.post("/api/chat", json={"question": "다른 사용자", "user_id": logged_in_user["id"]})
    assert response.status_code == 200

    # 각각의 대화가 실제 로그인 세션 소유자에게 귀속되었는지 확인
    assert [(chat.user_id, chat.question) for chat in read_chats()] == [
        (logged_in_user["id"], "첫 사용자"),
        (other_id, "다른 사용자"),
    ]


@pytest.mark.parametrize(
    "case, question, status",
    [("logout", "hello", 401), ("missing_header", "hello", 403),
     ("empty", " \n ", 422), ("too_long", "질" * 1001, 422)],
)
def test_rejected_request_does_not_call_ai_or_save(client, logged_in_user, ai_calls, case, question, status):
    """인증 실패, CSRF 헤더 누락, 입력값 검증 실패 시 AI가 호출되지 않고 DB에도 저장되지 않는지 검증합니다."""
    if case == "logout":
        assert client.post("/api/logout").status_code == 204
    elif case == "missing_header":
        client.headers.pop("X-Requested-With")
    assert client.post("/api/chat", json={"question": question}).status_code == status
    assert ai_calls == []
    assert read_chats() == []


def test_unreachable_ai_does_not_save(client, logged_in_user):
    """외부 AI 엔드포인트 연결 불가 시 502 오류를 반환하고 대화 기록을 DB에 저장하지 않는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "hello"}).status_code == 502
    assert read_chats() == []


@pytest.mark.parametrize(
    "error_name, status",
    [("AITimeoutError", 504), ("AIServiceError", 502)],
)
def test_ai_failure_does_not_save(client, logged_in_user, monkeypatch, error_name, status):
    """AI 타임아웃(504) 또는 서비스 장애(502) 발생 시 DB에 미완성 대화가 저장되지 않는지 검증합니다."""
    from app import llm_connect

    error_type = getattr(llm_connect, error_name)

    async def fail(question, history):
        raise error_type("test AI failure")

    monkeypatch.setattr(llm_connect, "generate_answer", fail)
    assert client.post("/api/chat", json={"question": "hello"}).status_code == status
    assert read_chats() == []


def test_unexpected_ai_error_does_not_save(client, logged_in_user, monkeypatch):
    """AI 통신 중 AIError가 아닌 예기치 못한 런타임 오류 발생 시에도 DB 저장이 차단되는지 검증합니다."""
    from app import llm_connect

    async def fail(question, history):
        raise RuntimeError("test AI failure")

    monkeypatch.setattr(llm_connect, "generate_answer", fail)
    with pytest.raises(RuntimeError, match="test AI failure"):
        client.post("/api/chat", json={"question": "hello"})
    assert read_chats() == []


def test_foreign_key_failure_rolls_back_and_session_can_be_reused(client, logged_in_user):
    """존재하지 않는 user_id 참조 시 외래키 제약조건 위반으로 롤백되고 세션이 정상 복원되는지 검증합니다."""
    from app.chat_db import create_chat
    from app.db_connect import SessionLocal

    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            create_chat(db, logged_in_user["id"] + 100, "question", ANSWER)
        assert not db.in_transaction()
        assert read_chats() == []
        chat_id = create_chat(db, logged_in_user["id"], "valid question", ANSWER)
    assert [chat.id for chat in read_chats()] == [chat_id]


def test_constraint_failure_returns_500_without_question(client, logged_in_user, monkeypatch, caplog):
    """DB 저장 제약조건 위반 시 500 에러가 반환되며 질문 원문이 로그나 응답에 노출되지 않는지 검증합니다."""
    from app import llm_connect

    async def invalid_answer(question, history):
        return None  # answer 컬럼은 NOT NULL이므로 제약조건 오류 유발

    monkeypatch.setattr(llm_connect, "generate_answer", invalid_answer)
    question = "로그에 남기지 않을 질문 내용"
    response = client.post("/api/chat", json={"question": question})
    assert response.status_code == 500
    assert response.json() == {"detail": "대화 기록을 저장하지 못했습니다."}
    assert read_chats() == []
    assert "db_save_failure operation=chat" in caplog.text
    assert "SQL parameters hidden" in caplog.text
    assert question not in caplog.text
    assert "INSERT" not in response.text


def test_commit_failure_rolls_back_and_next_chat_works(client, logged_in_user, ai_calls, monkeypatch, caplog):
    """트랜잭션 커밋 실패 시 자동 롤백되어 다음 대화 저장이 정상적으로 수행되는지 검증합니다."""
    caplog.set_level("INFO")

    def fail_commit(db):
        raise OperationalError("COMMIT", {}, SQLiteOperationalError("test commit failure"))

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        response = client.post("/api/chat", json={"question": "failed question"})
    assert response.status_code == 500
    assert response.json() == {"detail": "대화 기록을 저장하지 못했습니다."}
    assert read_chats() == []
    assert "db_save_failure operation=chat" in caplog.text
    assert "db_save_success operation=chat" not in caplog.text

    # 다음 요청 시 정상 작동 확인
    assert client.post("/api/chat", json={"question": "next question"}).status_code == 200
    assert [chat.question for chat in read_chats()] == ["next question"]
    assert ai_calls == [("failed question", []), ("next question", [])]


def test_existing_user_db_gets_chats_and_records_survive_restart(application, tmp_path):
    """기존 사용자 테이블만 있던 DB에 chats 테이블이 자동 추가되고 재기동 후에도 데이터가 보존되는지 검증합니다."""
    env = {
        **os.environ,
        "DATABASE_PATH": str(tmp_path / "upgrade.db"),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    }
    setup = """
from app.db_connect import engine
from app.models.user import User

# 이전 버전처럼 users 테이블만 있는 DB를 만든다.
User.__table__.create(engine)
with engine.begin() as connection:
    connection.execute(User.__table__.insert().values(username='existing', password_hash='test hash'))

from app.db_connect import init_db, SessionLocal
from app.chat_db import create_chat
init_db()
with SessionLocal() as db:
    assert create_chat(db, 1, 'saved question', 'saved answer') == 1
engine.dispose()
"""
    restarted = """
from sqlalchemy import inspect, select
from app.db_connect import engine, init_db, SessionLocal
from app.models.chat import Chat
from app.models.user import User

init_db()
assert set(inspect(engine).get_table_names()) == {'users', 'chats'}
assert any(index['column_names'] == ['user_id'] for index in inspect(engine).get_indexes('chats'))
with SessionLocal() as db:
    assert db.get(User, 1).username == 'existing'
    chats = db.scalars(select(Chat)).all()
    assert len(chats) == 1
    assert (chats[0].user_id, chats[0].question, chats[0].answer) == (1, 'saved question', 'saved answer')
engine.dispose()
"""
    for code in (setup, restarted):
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=tmp_path, env=env,
            text=True, capture_output=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
