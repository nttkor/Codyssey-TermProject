"""AI 통신 모듈과 채팅 API의 오류 변환·로그를 확인한다.

실제 제공자 대신 로컬 HTTP 서버를 게이트웨이로 사용한다.
OpenAI 호환 요청 본문이 그대로 전달되는지, 실패가 504·502로 바뀌는지 본다.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PASSWORD = "an example password"


class _GatewayHandler(BaseHTTPRequestHandler):
    """테스트가 지정한 방식으로 응답하는 최소한의 OpenAI 호환 게이트웨이."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")

        server = self.server
        server.requests.append(
            {"path": self.path, "authorization": self.headers.get("Authorization"), "body": body}
        )

        behaviour = server.behaviour
        if behaviour == "slow":
            # 클라이언트 타임아웃보다 오래 끈다.
            server.release.wait(timeout=10)
            return

        if behaviour == "error":
            payload = {"error": {"message": "invalid api key sk-secret-should-not-leak"}}
            raw = json.dumps(payload).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        content = "" if behaviour == "empty" else "게이트웨이 답변"
        payload = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": body.get("model", "test-model"),
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
        }
        if behaviour == "malformed":
            payload = server.payload
        raw = json.dumps(payload).encode()
        if behaviour == "invalid_json":
            raw = b'{"choices":'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        """테스트 출력에 HTTP 접근 로그를 남기지 않는다."""


@pytest.fixture
def gateway():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _GatewayHandler)
    server.requests = []
    server.behaviour = "ok"
    server.release = threading.Event()
    # 기본 poll_interval 0.5초는 shutdown()을 그만큼 기다리게 해 테스트마다 낭비된다.
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    server.base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def connect(gateway, monkeypatch):
    """llm_connect가 테스트 게이트웨이를 보도록 클라이언트와 설정만 바꾼다.

    모듈을 reload하면 예외 클래스가 새 객체가 되어 llm.py의 except 절이
    더 이상 같은 클래스를 잡지 못한다. 그래서 모듈 객체는 그대로 둔다.
    """
    from openai import AsyncOpenAI

    from app import llm_connect

    client = AsyncOpenAI(
        api_key="test-gateway-key",
        base_url=gateway.base_url,
        timeout=1.0,
        max_retries=0,
    )
    monkeypatch.setattr(llm_connect, "_client", client)
    monkeypatch.setattr(llm_connect, "AI_MODEL", "test-model")
    monkeypatch.setattr(llm_connect, "AI_TIMEOUT", 1.0)
    return llm_connect


@pytest.fixture
def logged_in(client):
    credentials = {"username": "ai_user", "password": PASSWORD}
    assert client.post("/api/signup", json=credentials).status_code == 201
    assert client.post("/api/login", json=credentials).status_code == 200


def test_request_uses_openai_chat_completions_format(client, logged_in, connect, gateway):
    response = client.post("/api/chat", json={"question": "첫 질문"})

    assert response.status_code == 200
    assert response.json() == {"answer": "게이트웨이 답변"}

    assert len(gateway.requests) == 1
    request = gateway.requests[0]
    assert request["path"].endswith("/chat/completions")
    assert request["authorization"] == "Bearer test-gateway-key"
    assert request["body"]["model"] == "test-model"
    assert request["body"]["messages"] == [{"role": "user", "content": "첫 질문"}]


def test_history_is_sent_before_current_question(client, logged_in, connect, gateway):
    assert client.post("/api/chat", json={"question": "질문 1"}).status_code == 200
    assert client.post("/api/chat", json={"question": "질문 2"}).status_code == 200

    assert gateway.requests[1]["body"]["messages"] == [
        {"role": "user", "content": "질문 1"},
        {"role": "assistant", "content": "게이트웨이 답변"},
        {"role": "user", "content": "질문 2"},
    ]


def test_question_is_not_duplicated_in_messages(client, logged_in, connect, gateway):
    assert client.post("/api/chat", json={"question": "중복 확인"}).status_code == 200

    contents = [message["content"] for message in gateway.requests[0]["body"]["messages"]]
    assert contents.count("중복 확인") == 1


def test_timeout_returns_504_and_does_not_save(client, logged_in, connect, gateway, caplog):
    gateway.behaviour = "slow"

    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "느린 질문"})

    assert response.status_code == 504
    assert "지연" in response.json()["detail"]
    assert client.get("/api/me/chats").json() == []
    assert any("ai_call_timeout" in record.message for record in caplog.records)


def test_provider_error_returns_502_and_hides_details(client, logged_in, connect, gateway, caplog):
    gateway.behaviour = "error"

    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "실패 질문"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "sk-secret-should-not-leak" not in detail
    assert "invalid api key" not in detail.lower()
    assert client.get("/api/me/chats").json() == []

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "ai_call_failure" in logged
    assert "sk-secret-should-not-leak" not in logged


def test_empty_answer_returns_502_and_does_not_save(client, logged_in, connect, gateway):
    gateway.behaviour = "empty"

    assert client.post("/api/chat", json={"question": "빈 답변"}).status_code == 502
    assert client.get("/api/me/chats").json() == []


def test_successful_answer_is_saved_and_listed(client, logged_in, connect, gateway):
    assert client.post("/api/chat", json={"question": "저장될 질문"}).status_code == 200

    chats = client.get("/api/me/chats").json()
    assert [(chat["question"], chat["answer"]) for chat in chats] == [
        ("저장될 질문", "게이트웨이 답변")
    ]


def test_logs_do_not_contain_key_or_message_bodies(client, logged_in, connect, gateway, caplog):
    with caplog.at_level(logging.INFO):
        assert client.post("/api/chat", json={"question": "비밀 질문"}).status_code == 200

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "ai_call_started" in logged
    assert "ai_call_success" in logged
    assert "test-gateway-key" not in logged
    assert "비밀 질문" not in logged
    assert "게이트웨이 답변" not in logged


def test_unauthenticated_request_does_not_call_gateway(client, connect, gateway):
    assert client.post("/api/chat", json={"question": "비로그인"}).status_code == 401
    assert gateway.requests == []


def test_invalid_question_does_not_call_gateway(client, logged_in, connect, gateway):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
    assert gateway.requests == []


def test_server_recovers_after_failed_call(client, logged_in, connect, gateway):
    gateway.behaviour = "error"
    assert client.post("/api/chat", json={"question": "실패"}).status_code == 502

    gateway.behaviour = "ok"
    assert client.post("/api/chat", json={"question": "복구"}).status_code == 200
    assert [chat["question"] for chat in client.get("/api/me/chats").json()] == ["복구"]


@pytest.mark.parametrize("payload", [
    None, [], {}, {"choices": []}, {"choices": [None]},
    {"choices": [{"message": None}]},
    {"choices": [{"message": {"content": 123}}]},
    {"choices": [{"message": {"content": ["private-answer"]}}]},
    {"choices": [{"message": {"content": "  "}}]},
])
def test_malformed_success_response_is_safe_and_recovers(
    client, logged_in, connect, gateway, caplog, payload,
):
    gateway.behaviour = "malformed"
    gateway.payload = payload
    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "private-question"})
    assert response.status_code == 502
    assert client.get("/api/me/chats").json() == []
    assert "ai_call_failure" in caplog.text
    for secret in ("private-question", "private-answer", "test-gateway-key"):
        assert secret not in response.text
        assert secret not in caplog.text
    gateway.behaviour = "ok"
    assert client.post("/api/chat", json={"question": "복구"}).status_code == 200
    assert [chat["question"] for chat in client.get("/api/me/chats").json()] == ["복구"]


def test_invalid_json_response_is_safe(client, logged_in, connect, gateway, caplog):
    gateway.behaviour = "invalid_json"
    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "형식 오류"})
    assert response.status_code == 502
    assert "ai_call_failure" in caplog.text
    assert client.get("/api/me/chats").json() == []
