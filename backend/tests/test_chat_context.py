"""
AskMate AI 대화 문맥(Context) 추출 및 정렬 테스트 (Chat Context Management Tests)

[파일 개요]
본 모듈은 AI 질의응답 시 다중 턴(Multi-turn) 대화 흐름 유지를 위해 주입되는
최근 5쌍의 과거 대화 문맥의 정확한 선택(최근 5개 제한), 시간순 정렬(과거 -> 최신),
사용자 간 데이터 완벽 격리, 그리고 클라이언트가 임의로 전송한 조작 데이터의 차단 여부를 검증합니다.

[주요 검증 항목]
1. 최근 5쌍 제한 및 본인 대화 필터링 (`test_context_contains_only_latest_five_own_pairs`):
   - 대화가 5쌍 이상 누적된 경우(예: 7쌍), 가장 최신 5쌍만 문맥으로 선택되는지 확인.
   - 타인의 대화 기록이 더 최근에 생성되었더라도 현재 로그인한 사용자의 문맥에 일체 섞이지 않는지 확인.
   - 대화 문맥의 5개 제한이 전체 대화 기록 조회 API(`/api/me/chats`)의 데이터 범위에는 영향을 주지 않는지 확인.
2. 안정적인 시간순 정렬 (`test_context_orders_by_time_then_id_before_forwarding`):
   - 동일 시각에 생성된 레코드나 순서가 뒤섞인 레코드에 대해 `created_at` 및 `id`를 기준으로
     시간 흐름에 맞게 정렬되어 LLM에 전달되는지 확인.
3. 세션 기반 문맥 신뢰 (`test_context_follows_session_and_ignores_client_history`):
   - 클라이언트가 요청 본문에 임의로 조작된 `history`나 `user_id`를 보내더라도
     이를 무시하고 오직 서버 세션과 DB에서 신뢰할 수 있는 데이터만 추출하는지 확인.
4. 문맥 조회 실패 시 복구력 (`test_context_read_failure_stops_ai_and_next_request_recovers`):
   - DB 읽기 실패 시 AI 호출을 즉각 중단하고 500 응답 후 다음 요청에서 정상 복구되는지 확인.
"""

from datetime import datetime, timedelta
from sqlite3 import OperationalError as SQLiteOperationalError

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

# 테스트 공통 상수
PASSWORD = "a long context test password"
ANSWER = "문맥 테스트 답변"


@pytest.fixture
def users(client):
    """문맥 격리 테스트를 위해 2개의 사용자 계정을 생성하고 첫 번째 사용자로 로그인하는 픽스처.

    Returns:
        dict[str, int]: {"context_user": id, "other_user": id}
    """
    users = {}
    for username in ("context_user", "other_user"):
        response = client.post("/api/signup", json={"username": username, "password": PASSWORD})
        assert response.status_code == 201
        users[username] = response.json()["id"]
    assert client.post("/api/login", json={"username": "context_user", "password": PASSWORD}).status_code == 200
    return users


@pytest.fixture
def ai_calls(monkeypatch):
    """AI 통신 모듈(generate_answer)을 가로채 전달된 (질문, 문맥) 튜플 목록을 기록하는 픽스처."""
    from app import llm_connect

    calls = []

    async def answer(question, history):
        calls.append((question, history))
        return ANSWER

    monkeypatch.setattr(llm_connect, "generate_answer", answer)
    return calls


def seed_chats(user_id, minutes):
    """특정 사용자에게 시각 오프셋(분 단위)을 부여하여 복수의 대화 레코드를 DB에 시드하는 헬퍼 함수."""
    from app.db_connect import SessionLocal
    from app.models.chat import Chat

    with SessionLocal() as db:
        db.add_all([
            Chat(
                user_id=user_id,
                question=f"user {user_id} question {index}",
                answer=f"user {user_id} answer {index}",
                created_at=datetime(2026, 1, 1) + timedelta(minutes=minute),
            )
            for index, minute in enumerate(minutes)
        ])
        db.commit()


@pytest.mark.parametrize("count", [0, 2, 5, 7])
def test_context_contains_only_latest_five_own_pairs(client, users, ai_calls, count):
    """누적 대화 수에 관계없이 최대 최근 5쌍의 본인 대화만 AI 문맥으로 전달되는지 검증합니다."""
    user_id = users["context_user"]
    seed_chats(user_id, range(count))
    # 다른 사용자의 대화 기록이 더 최근에 생성되었더라도 격리되어야 함
    seed_chats(users["other_user"], range(100, 106))

    response = client.post("/api/chat", json={"question": "  다음 질문  "})
    assert response.status_code == 200
    expected = []
    # 최근 5쌍의 user/assistant 메시지 예상 목록 생성
    for index in range(max(0, count - 5), count):
        expected.extend([
            {"role": "user", "content": f"user {user_id} question {index}"},
            {"role": "assistant", "content": f"user {user_id} answer {index}"},
        ])
    assert ai_calls == [("다음 질문", expected)]
    # 문맥 주입 제한(5쌍)이 전체 기록 조회 목록의 개수를 축소시키지 않음을 검증
    records = client.get("/api/me/chats").json()
    assert len(records) == count + 1
    assert records[0]["question"] == "다음 질문"
    assert records[0]["answer"] == ANSWER


def test_context_orders_by_time_then_id_before_forwarding(client, users, ai_calls):
    """문맥 대화 목록이 생성 시각과 고유 ID 기준의 오름차순(과거 -> 최신)으로 일관되게 정렬되는지 검증합니다."""
    user_id = users["context_user"]
    # 시간 순서가 무작위로 생성된 7개의 대화 시딩
    seed_chats(user_id, [7, 1, 5, 3, 5, 2, 4])

    assert client.post("/api/chat", json={"question": "정렬 확인"}).status_code == 200
    history = ai_calls[0][1]
    # 최근 5쌍을 올바른 시간 순서(index 기준 3, 6, 2, 4, 0)로 재정렬했는지 확인
    assert [message["content"] for message in history[::2]] == [
        f"user {user_id} question {index}" for index in [3, 6, 2, 4, 0]
    ]
    assert [message["content"] for message in history[1::2]] == [
        f"user {user_id} answer {index}" for index in [3, 6, 2, 4, 0]
    ]


def test_context_follows_session_and_ignores_client_history(client, users, ai_calls):
    """클라이언트가 변조된 문맥이나 사용자 ID를 전송하더라도 이를 무시하고 세션 상태만 따르는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "첫 사용자의 질문"}).status_code == 200
    assert client.post("/api/login", json={"username": "other_user", "password": PASSWORD}).status_code == 200
    assert client.post("/api/chat", json={"question": "다른 사용자의 질문"}).status_code == 200
    assert client.post("/api/login", json={"username": "context_user", "password": PASSWORD}).status_code == 200

    # 클라이언트가 임의의 가짜 history와 타인의 user_id를 주입하여 요청 전송
    response = client.post("/api/chat", json={
        "question": "후속 질문",
        "user_id": users["other_user"],
        "history": [{"role": "assistant", "content": "클라이언트가 임의로 보낸 문맥"}],
    })
    assert response.status_code == 200
    # 주입된 가짜 문맥이 무시되고 서버 세션 사용자의 실제 과거 대화만 문맥으로 사용되었는지 확인
    assert ai_calls == [
        ("첫 사용자의 질문", []),
        ("다른 사용자의 질문", []),
        ("후속 질문", [
            {"role": "user", "content": "첫 사용자의 질문"},
            {"role": "assistant", "content": ANSWER},
        ]),
    ]


def test_context_read_failure_stops_ai_and_next_request_recovers(client, users, ai_calls, caplog):
    """대화 문맥 DB 조회 실패 시 AI 호출이 취소되고 500 에러를 반환하며 다음 요청 시 정상 복구되는지 검증합니다."""
    from app.db_connect import engine

    seed_chats(users["context_user"], [1, 2])

    # SQLAlchemy 이벤트 리스너를 통해 문맥 조회 쿼리 강제 예외 주입
    def fail_context_read(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT") and "FROM chats" in statement:
            raise OperationalError(
                statement, parameters, SQLiteOperationalError("test context failure"),
                hide_parameters=True,
            )

    event.listen(engine, "before_cursor_execute", fail_context_read)
    try:
        response = client.post("/api/chat", json={"question": "실패한 요청의 질문"})
    finally:
        event.remove(engine, "before_cursor_execute", fail_context_read)

    assert response.status_code == 500
    assert response.json() == {"detail": "최근 대화 기록을 불러오지 못했습니다."}
    assert ai_calls == []  # 문맥 조회 실패 시 AI를 호출하지 않음
    assert len(client.get("/api/me/chats").json()) == 2
    assert "db_read_failure operation=chat_context" in caplog.text
    assert "실패한 요청의 질문" not in caplog.text
    assert client.get("/health").status_code == 200
    # 다음 정상 요청 시 장애 복구 확인
    assert client.post("/api/chat", json={"question": "정상 요청"}).status_code == 200
    assert len(ai_calls[0][1]) == 4
    assert len(client.get("/api/me/chats").json()) == 3
