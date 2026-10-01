"""
AskMate 대화 기록 조회 API 통합 테스트 (Chat History API Tests)

[파일 개요]
본 모듈은 대화 기록 조회 엔드포인트(`/api/me/chats`)의 사용자 격리(IDOR 방어),
복합 정렬(생성 시각 및 ID 내림차순)의 일관성, ISO 8601 UTC 타임스탬프 직렬화 규격,
비인가 접근 차단, DB 조회 장애 처리, 영구 보존 및 검증용 SQL 스크립트와의 정합성을 테스트합니다.

[주요 검증 항목]
1. 안정적인 최신순 정렬 및 본인 데이터 격리 (`test_history_returns_only_own_records_in_stable_latest_order`):
   - 마이크로초 단위의 동일 시각 레코드 발생 시에도 `id DESC`를 통해 결정론적(Deterministic) 정렬 순서를 보장하는지 확인.
   - 타인의 대화 기록이 일체 포함되지 않고 본인의 레코드만 반환되는지 확인.
   - 시각 데이터가 ISO 8601 UTC 표준 문자열('Z' 접미사)로 변환되는지 확인.
2. 쿼리 파라미터 변조(IDOR) 방어 (`test_query_user_id_cannot_change_record_owner`):
   - URL 파라미터(`?user_id=...`)를 통해 타인의 대화 열람을 시도하더라도
     이를 철저히 무시하고 세션에 인증된 사용자의 데이터만 응답하는지 확인.
3. 세션 무효화 및 접근 제어 (`test_invalid_session_cannot_read_records`):
   - 익명(`anonymous`), 로그아웃(`logged_out`), 쿠키 변조(`tampered`), 만료(`expired`) 상태에서
     모두 401 Unauthorized로 조회 권한이 차단되는지 확인.
4. 검증용 SQL 쿼리 정합성 (`test_verification_sql_filters_users_and_matches_api_order`):
   - 운영/검증용 스크립트인 `backend/scripts/check_logs.sql`을 직접 실행했을 때의 조회 결과가
     `/api/me/chats` API의 응답 순서 및 필터링 결과와 100% 일치하는지 확인.
5. OpenAPI 문서화 정합성 (`test_history_openapi_documents_array_and_datetime`):
   - Swagger/OpenAPI 스키마에 응답 타입(배열, date-time 포맷)이 정확히 기술되어 있는지 확인.
"""

from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

# 테스트 공통 상수
PASSWORD = "a long history password"
COOKIE = "askmate_session"


@pytest.fixture
def users(client):
    """대화 기록 격리 검증을 위해 3명의 사용자를 생성하고 첫 번째 사용자로 로그인하는 픽스처.

    Returns:
        dict[str, int]: {"history_user": id, "another_user": id, "empty_user": id}
    """
    result = {}
    for username in ("history_user", "another_user", "empty_user"):
        response = client.post("/api/signup", json={"username": username, "password": PASSWORD})
        assert response.status_code == 201
        result[username] = response.json()["id"]
    assert client.post("/api/login", json={"username": "history_user", "password": PASSWORD}).status_code == 200
    return result


@pytest.fixture
def records(client, users):
    """마이크로초 단위 동일 시각 및 사용자별 대화 레코드를 데이터베이스에 직접 시드하는 픽스처."""
    from app.db_connect import SessionLocal
    from app.models.chat import Chat

    with SessionLocal() as db:
        db.add_all([
            Chat(user_id=users["history_user"], question="새 질문", answer="새 답변",
                 created_at=datetime(2026, 9, 20, 3, 0, 0, 123456)),
            Chat(user_id=users["history_user"], question="이전 질문", answer="이전 답변",
                 created_at=datetime(2026, 9, 19, 3, 0)),
            Chat(user_id=users["history_user"], question="같은 시각의 질문", answer="같은 시각의 답변",
                 created_at=datetime(2026, 9, 20, 3, 0, 0, 123456)),
            Chat(user_id=users["another_user"], question="다른 사용자의 질문", answer="다른 사용자의 답변",
                 created_at=datetime(2026, 9, 21, 3, 0)),
        ])
        db.commit()


def test_history_returns_only_own_records_in_stable_latest_order(client, records, caplog):
    """본인 대화만 반환되며, 동일 시각 레코드도 ID 역순으로 안정적인 최신순 정렬을 유지하는지 검증합니다."""
    response = client.get("/api/me/chats")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    # 동일 시각인 경우 id가 더 큰(나중에 생성된) 3번이 1번보다 먼저 정렬됨을 확인
    assert response.json() == [
        {"id": 3, "question": "같은 시각의 질문", "answer": "같은 시각의 답변", "created_at": "2026-09-20T03:00:00.123456Z"},
        {"id": 1, "question": "새 질문", "answer": "새 답변", "created_at": "2026-09-20T03:00:00.123456Z"},
        {"id": 2, "question": "이전 질문", "answer": "이전 답변", "created_at": "2026-09-19T03:00:00Z"},
    ]
    assert "set-cookie" not in response.headers
    # 개인 대화 내용이 감사 로그에 남지 않는지 확인
    for record in response.json():
        assert record["question"] not in caplog.text
        assert record["answer"] not in caplog.text


def test_query_user_id_cannot_change_record_owner(client, users, records):
    """쿼리 파라미터로 타인의 user_id를 주입해도 오직 세션 소유자의 기록만 반환되는지(IDOR 방지) 검증합니다."""
    # history_user 세션에서 another_user의 id를 조회 파라미터로 전송
    response = client.get("/api/me/chats", params={"user_id": users["another_user"]})
    assert response.status_code == 200
    assert [record["id"] for record in response.json()] == [3, 1, 2]

    # another_user로 로그인 후 history_user의 id를 쿼리로 전송
    assert client.post("/api/login", json={"username": "another_user", "password": PASSWORD}).status_code == 200
    response = client.get("/api/me/chats", params={"user_id": users["history_user"]})
    assert [record["id"] for record in response.json()] == [4]


def test_user_without_records_gets_empty_array_without_post_header(client, records):
    """대화 기록이 없는 사용자의 경우 빈 배열([])이 반환되고 GET 요청에는 CSRF 헤더가 불필요함을 검증합니다."""
    assert client.post("/api/login", json={"username": "empty_user", "password": PASSWORD}).status_code == 200
    client.headers.pop("X-Requested-With")  # CSRF 헤더 제거
    response = client.get("/api/me/chats")
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("state", ["anonymous", "logged_out", "tampered", "expired"])
def test_invalid_session_cannot_read_records(client, records, monkeypatch, state):
    """비로그인, 로그아웃, 쿠키 변조, 만료 상태에서 대화 기록 접근이 모두 401로 차단되는지 검증합니다."""
    if state == "anonymous":
        client.cookies.clear()
    elif state == "logged_out":
        assert client.post("/api/logout").status_code == 204
    elif state == "tampered":
        cookie = client.cookies.get(COOKIE)
        client.cookies.clear()
        client.cookies.set(COOKIE, cookie + "invalid")
    else:
        now = TimestampSigner.get_timestamp
        monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: now(self) + 3601)
    response = client.get("/api/me/chats")
    assert response.status_code == 401
    assert response.json() == {"detail": "로그인이 필요합니다."}


def test_query_failure_returns_500_and_next_request_recovers(client, records, caplog):
    """DB 쿼리 실행 실패 시 500 에러를 반환하고 세부 SQL 오류를 은닉하며 다음 요청 시 정상 복구되는지 검증합니다."""
    from app.db_connect import engine

    def fail_read(connection, cursor, statement, parameters, context, executemany):
        if "FROM chats" in statement:
            raise OperationalError(statement, parameters, sqlite3.OperationalError("test read failure"), hide_parameters=True)

    event.listen(engine, "before_cursor_execute", fail_read)
    try:
        response = client.get("/api/me/chats")
    finally:
        event.remove(engine, "before_cursor_execute", fail_read)
    assert response.status_code == 500
    assert response.json() == {"detail": "대화 기록을 불러오지 못했습니다."}
    assert "db_read_failure operation=history" in caplog.text
    assert "test read failure" not in response.text
    assert "같은 시각의 질문" not in caplog.text
    assert "같은 시각의 답변" not in caplog.text

    # 복구 확인
    recovered = client.get("/api/me/chats")
    assert recovered.status_code == 200
    assert len(recovered.json()) == 3


def test_saved_chat_is_visible_through_history_api(client, users, monkeypatch):
    """신규 대화 완료 후 대화 기록 API를 통해 해당 질문과 답변이 즉시 조회되는지 검증합니다."""
    from app import llm_connect

    async def answer(question, history):
        return "저장 후 조회할 답변\n두 번째 줄"

    monkeypatch.setattr(llm_connect, "generate_answer", answer)
    saved = client.post("/api/chat", json={"question": "  저장 후 조회할 질문  "})
    assert saved.status_code == 200
    response = client.get("/api/me/chats")
    assert response.status_code == 200
    record, = response.json()
    assert record["question"] == "저장 후 조회할 질문"
    assert record["answer"] == saved.json()["answer"]
    assert datetime.fromisoformat(record["created_at"]).tzinfo is UTC


def test_records_can_be_read_after_app_restart(application, client, records):
    """서버가 재기동되더라도 과거 대화 기록이 영구 보존되어 정확히 동일하게 조회되는지 검증합니다."""
    before = client.get("/api/me/chats").json()
    with TestClient(application) as restarted:
        restarted.cookies.set(COOKIE, client.cookies.get(COOKIE))
        response = restarted.get("/api/me/chats")
        assert response.status_code == 200
        assert response.json() == before


def test_verification_sql_filters_users_and_matches_api_order(client, users, records):
    """확인용 SQL 스크립트(check_logs.sql)의 쿼리 결과가 API의 정렬 순서 및 데이터와 완벽히 일치하는지 검증합니다."""
    from app.config import DATABASE_PATH

    query = (Path(__file__).resolve().parents[1] / "scripts/check_logs.sql").read_text()
    with sqlite3.connect(DATABASE_PATH) as connection:
        for username, expected_ids in [("history_user", [3, 1, 2]), ("another_user", [4]), ("empty_user", [])]:
            rows = connection.execute(query, {"user_id": users[username]}).fetchall()
            assert [row[0] for row in rows] == expected_ids
            assert all(row[1] == users[username] for row in rows)


def test_history_openapi_documents_array_and_datetime(client):
    """OpenAPI 스키마 문서에 대화 기록 응답이 배열 및 필수 속성을 포함하여 기술되어 있는지 검증합니다."""
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/me/chats"]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["type"] == "array"
    model_name = response["items"]["$ref"].split("/")[-1]
    model = schema["components"]["schemas"][model_name]
    assert set(model["required"]) == {"id", "question", "answer", "created_at"}
    assert model["properties"]["created_at"]["format"] == "date-time"
    assert not any(parameter["name"] == "user_id" for parameter in operation.get("parameters", []))
