"""
AskMate 로그인·세션·접근 제어 통합 테스트 (Login, Session & Access Control Tests)

[파일 개요]
본 모듈은 인증(`/api/login`), 세션 쿠키 관리, 본인 정보 조회(`/api/me`), 로그아웃(`/api/logout`),
CSRF 방어 헤더 검증, 브라우저 다중 세션 격리, 변조되거나 만료된 쿠키 방어,
그리고 보호된 페이지(`/chat`, `/history`)의 접근 권한 제어 로직을 실전 테스트합니다.

[주요 검증 항목]
1. 세션 쿠키 보안 속성 (`test_login_and_current_user`):
   - 로그인 성공 시 발급되는 세션 쿠키의 `HttpOnly`, `SameSite=Lax`, `Max-Age`, `Path=/` 속성 확인.
   - `Cache-Control: no-store` 헤더를 통해 세션 정보가 브라우저나 프록시에 캐싱되지 않음을 확인.
   - 세션 쿠키 복호화 시 `user_id`가 정확히 보관되며 로그에 민감정보가 노출되지 않는지 확인.
2. 비인가 및 변조 공격 방어 (`test_invalid_credentials`, `test_invalid_cookies_are_anonymous`):
   - 잘못된 비밀번호, 대소문자 불일치, 비밀번호 공백 변경 시 401 차단.
   - 서명 키 불일치(`wrong_key`), 페이로드 변조(`tampered`), 유효기간 만료(`expired`) 쿠키에 대해
     익명 사용자로 간주하여 접근을 차단하는지 확인.
3. CSRF 및 교차 출처 공격 방어 (`test_post_requires_csrf_header`, `test_cross_origin_preflight_is_not_allowed`):
   - 상태 변경 POST 요청에서 `X-Requested-With: XMLHttpRequest` 누락 시 403 Forbidden 차단.
   - 외부 출처(Cross-origin)의 OPTIONS 사전 요청(Preflight)에 대해 405 Method Not Allowed 반환.
4. 페이지 접근 제어 (`test_protected_pages`):
   - 비인가 사용자의 보호 페이지 접근 시 303 리다이렉트(`/login`) 처리.
   - 로그인 완료 사용자의 로그인 화면 재접근 시 303 리다이렉트(`/chat`) 처리.
"""

from base64 import b64decode
import json
from sqlite3 import OperationalError as SQLiteOperationalError
import time

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

# 테스트용 공통 상수
PASSWORD = "  a long password phrase  "
CREDENTIALS = {"username": "charles", "password": PASSWORD}
COOKIE = "askmate_session"


@pytest.fixture
def registered_user(client):
    """테스트용 계정을 사전 가입시키는 픽스처 함수.

    Returns:
        dict: 생성된 사용자의 응답 정보 {"id": int, "username": str}
    """
    response = client.post("/api/signup", json=CREDENTIALS)
    assert response.status_code == 201
    return response.json()


def test_login_and_current_user(client, registered_user, caplog):
    """정상 로그인 후 세션 쿠키가 보안 속성과 함께 발급되고 /api/me 조회가 가능한지 검증합니다."""
    from app.db_connect import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        original_hash = db.scalar(select(User.password_hash))
    caplog.set_level("INFO")
    response = client.post("/api/login", json={"username": " CHARLES ", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == registered_user
    cookie_header = response.headers["set-cookie"].lower()
    # 쿠키 보안 플래그 검증
    assert all(flag in cookie_header for flag in ("httponly", "samesite=lax", "path=/", "max-age=3600"))
    assert "secure" not in cookie_header  # 테스트 환경(HTTP)에서는 secure 제외 확인
    assert response.headers["cache-control"] == "no-store"

    # 세션 쿠키 내 user_id 페이로드 디코딩 검증
    cookie = client.cookies.get(COOKIE)
    assert json.loads(b64decode(cookie.split(".")[0])) == {"user_id": registered_user["id"]}

    # /api/me 엔드포인트 조회
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == registered_user
    assert me.headers["cache-control"] == "no-store"
    assert "set-cookie" not in me.headers  # 단순 조회 시 세션 만료 시각을 불필요하게 갱신하지 않음
    with SessionLocal() as db:
        assert db.scalar(select(User.password_hash)) == original_hash
    assert "login_success user_id=" in caplog.text
    # 로그 및 응답 본문 내 민감정보 비노출 확인
    for secret in (PASSWORD, original_hash, cookie):
        assert secret not in caplog.text
        assert secret not in response.text


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "unknown", "password": PASSWORD},
        {"username": "charles", "password": "wrong password"},
        {"username": "charles", "password": PASSWORD.strip()},
        {"username": "charles", "password": PASSWORD.upper()},
    ],
)
def test_invalid_credentials(client, registered_user, credentials, caplog):
    """존재하지 않는 사용자나 잘못된 비밀번호 입력 시 401 Unauthorized가 반환되는지 검증합니다."""
    response = client.post("/api/login", json=credentials)
    assert response.status_code == 401
    assert response.json() == {"detail": "사용자명 또는 비밀번호가 올바르지 않습니다."}
    assert "set-cookie" not in response.headers
    assert client.get("/api/me").status_code == 401
    assert "login_failure" in caplog.text
    assert credentials["password"] not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "charles"},
        {"password": PASSWORD},
        {"username": "   ", "password": PASSWORD},
        {"username": "charles", "password": ""},
        {"username": "charles", "password": "p" * 129},
        {"username": "charles", "password": 123},
        {"username": "charles", "password": {"secret": PASSWORD}},
        [PASSWORD],
    ],
)
def test_login_validation_does_not_echo_input(client, payload):
    """로그인 요청 본문 검증 실패 시 입력값이 응답에 에코되지 않는지 검증합니다."""
    response = client.post("/api/login", json=payload)
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert all(set(error) == {"type", "loc", "msg"} for error in response.json()["detail"])
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("password", ["p" * 15, "p" * 128, "공백과 유니코드를 포함한 비밀번호입니다"])
def test_signup_passwords_can_log_in(client, password):
    """회원가입 시 허용된 다양한 형태의 유효 비밀번호가 정상적으로 로그인되는지 검증합니다."""
    credentials = {"username": "boundary_user", "password": password}
    assert client.post("/api/signup", json=credentials).status_code == 201
    assert client.post("/api/login", json=credentials).status_code == 200


def test_logout_and_repeated_logout(client, registered_user, caplog):
    """로그아웃 시 세션이 만료되고 연속 로그아웃 호출 시에도 멱등하게 204가 반환되는지 검증합니다."""
    caplog.set_level("INFO")
    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    response = client.post("/api/logout")
    assert response.status_code == 204
    assert response.content == b""
    assert "expires=Thu, 01 Jan 1970" in response.headers["set-cookie"]
    assert client.cookies.get(COOKIE) is None
    assert client.get("/api/me").status_code == 401
    assert client.get("/chat", follow_redirects=False).headers["location"] == "/login"
    assert client.post("/api/chat", json={"question": "hello"}).status_code == 401
    # 멱등성 검증: 이미 로그아웃된 상태에서 재호출해도 204 정상 반환
    assert client.post("/api/logout").status_code == 204
    assert "logout_success user_id=" in caplog.text


def test_browsers_and_account_switching(application, client, registered_user, csrf_headers):
    """서로 다른 클라이언트(브라우저) 간 세션이 안전하게 격리되고 계정 전환이 가능한지 검증합니다."""
    other_credentials = {"username": "another", "password": PASSWORD}
    other_user = client.post("/api/signup", json=other_credentials).json()
    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    with TestClient(application, headers=csrf_headers) as second_browser:
        assert second_browser.get("/api/me").status_code == 401
        assert second_browser.post("/api/login", json=other_credentials).status_code == 200
        # 첫 번째 브라우저는 다른 브라우저의 세션에 영향을 받지 않음
        assert client.get("/api/me?user_id=" + str(other_user["id"])).json() == registered_user
        assert client.post("/api/login", json=other_credentials).status_code == 200
        assert client.get("/api/me").json() == other_user
        assert client.post("/api/logout").status_code == 204
        assert second_browser.get("/api/me").json() == other_user


@pytest.mark.parametrize("cookie_kind", ["tampered", "expired", "wrong_key"])
def test_invalid_cookies_are_anonymous(client, registered_user, monkeypatch, cookie_kind):
    """변조되었거나, 만료되었거나, 잘못된 서명 키를 가진 세션 쿠키는 비로그인으로 처리되는지 검증합니다."""
    from app.config import SESSION_SECRET_KEY

    if cookie_kind == "expired":
        issued_at = int(time.time()) - 3601
        with monkeypatch.context() as patch:
            patch.setattr(TimestampSigner, "get_timestamp", lambda self: issued_at)
            assert client.post("/api/login", json=CREDENTIALS).status_code == 200
        cookie = client.cookies.get(COOKIE)
    else:
        assert client.post("/api/login", json=CREDENTIALS).status_code == 200
        cookie = client.cookies.get(COOKIE)
        if cookie_kind == "tampered":
            cookie = "A" + cookie[1:]
        else:
            data = TimestampSigner(SESSION_SECRET_KEY).unsign(cookie)
            cookie = TimestampSigner("different-test-key").sign(data).decode()
    client.cookies.clear()
    client.cookies.set(COOKIE, cookie)
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/chat", json={"question": "hello"}).status_code == 401
    assert client.get("/history", follow_redirects=False).headers["location"] == "/login"


def test_deleted_user_loses_access(client, registered_user):
    """세션이 남아있더라도 DB에서 사용자가 삭제된 경우 즉시 401 처리되고 세션이 정리되는지 검증합니다."""
    from app.db_connect import SessionLocal
    from app.models.user import User

    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    with SessionLocal() as db:
        db.delete(db.get(User, registered_user["id"]))
        db.commit()
    assert client.get("/api/me").status_code == 401
    assert client.cookies.get(COOKIE) is None


@pytest.mark.parametrize("path", ["/chat", "/history"])
def test_protected_pages(client, registered_user, path):
    """인증 보호된 웹 페이지 화면의 303 리다이렉트 및 로그인 후 정상 접근을 검증합니다."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("text/html")
    assert client.get("/login", follow_redirects=False).headers["location"] == "/chat"


def test_unauthenticated_request_never_calls_ai(client, registered_user, monkeypatch):
    """비로그인 상태의 질문 요청 시 AI 통신 모듈이 호출되지 않고 사전에 401로 차단되는지 검증합니다."""
    from app import llm_connect

    questions = []

    async def answer(question, history):
        questions.append(question)
        return "test answer"

    monkeypatch.setattr(llm_connect, "generate_answer", answer)
    response = client.post("/api/chat", json={"question": "hello", "user_id": registered_user["id"]})
    assert response.status_code == 401
    assert questions == []
    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    response = client.post("/api/chat", json={"question": "hello"})
    assert response.status_code == 200
    assert response.json() == {"answer": "test answer"}
    assert questions == ["hello"]


@pytest.mark.parametrize("path", ["/api/signup", "/api/login", "/api/logout", "/api/chat"])
@pytest.mark.parametrize("header", [None, "wrong-value"])
def test_post_requires_csrf_header(client, registered_user, path, header):
    """상태 변경 POST 요청 시 올바른 CSRF 헤더가 없으면 403 Forbidden으로 거부되는지 검증합니다."""
    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    client.headers.pop("X-Requested-With")
    headers = {} if header is None else {"X-Requested-With": header}
    response = client.post(path, json={**CREDENTIALS, "question": "hello"}, headers=headers)
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert client.get("/api/me").json() == registered_user


def test_cross_origin_preflight_is_not_allowed(client):
    """타 출처(Cross-origin)의 CORS 사전 요청(OPTIONS)이 허용되지 않는지 검증합니다."""
    response = client.options("/api/login", headers={
        "Origin": "https://another.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Requested-With, Content-Type",
    })
    assert response.status_code == 405
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("operation", ["login", "session"])
def test_db_error_is_not_reported_as_invalid_credentials(client, registered_user, monkeypatch, caplog, operation):
    """DB 오류 발생 시 401(비밀번호 오류)이 아닌 500 상태 코드로 구분되어 반환되는지 검증합니다."""
    from app import account, auth

    assert client.post("/api/login", json=CREDENTIALS).status_code == 200

    def fail_lookup(*args):
        raise OperationalError("SELECT users", {}, SQLiteOperationalError("test DB failure"))

    target, name = (account, "get_user_by_username") if operation == "login" else (auth, "get_user_by_id")
    with monkeypatch.context() as patch:
        patch.setattr(target, name, fail_lookup)
        response = client.post("/api/login", json=CREDENTIALS) if operation == "login" else client.get("/api/me")
    assert response.status_code == 500
    assert response.json() == {"detail": "로그인 정보를 확인하지 못했습니다."}
    assert f"db_read_failure operation={operation}" in caplog.text
    assert "test DB failure" not in response.text
    assert PASSWORD not in caplog.text
    assert client.get("/api/me").json() == registered_user


def test_session_survives_app_restart(application, client, registered_user, csrf_headers):
    """서버 재시작 후에도 동일한 세션 쿠키로 계속 인증 상태가 유지되는지 검증합니다."""
    assert client.post("/api/login", json=CREDENTIALS).status_code == 200
    cookie = client.cookies.get(COOKIE)
    with TestClient(application, headers=csrf_headers) as restarted:
        restarted.cookies.set(COOKIE, cookie)
        assert restarted.get("/api/me").json() == registered_user
