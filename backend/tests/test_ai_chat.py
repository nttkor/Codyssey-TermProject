"""
AskMate AI 통신 및 채팅 API 통합 테스트 (AI Gateway Integration & Error Handling Tests)

[파일 개요]
본 모듈은 실제 외부 유료 AI API를 직접 호출하는 대신, 테스트 프로세스 내에서 가동되는
경량 멀티스레드 HTTP 서버(`ThreadingHTTPServer`)를 모의 OpenAI 게이트웨이로 활용하여,
OpenAI Chat Completions 규격 준수 여부, 에러 상태 코드 매핑(504, 502),
민감정보(API 키, 대화 원문) 로그 비노출, 그리고 비정상 응답 시의 안전한 복구 동작을 검증합니다.

[주요 검증 항목]
1. OpenAI API 규격 정합성 (`test_request_uses_openai_chat_completions_format` 등):
   - 경로(`/chat/completions`), 인증 헤더(`Bearer test-gateway-key`), 모델명, messages 구조 확인.
   - 이전 대화 문맥(`history`)이 시간 순서대로 먼저 전달되고 최신 질문이 마지막에 추가되는지 확인.
   - 메시지 배열 내에 동일 질문이 중복 포함되지 않는지 확인.
2. 장애 격리 및 HTTP 상태 코드 매핑:
   - 게이트웨이 응답 지연 시 HTTP 504 Gateway Timeout 반환 (`test_timeout_returns_504_...`).
   - 공급자 401/500 에러 및 JSON 형식 오류 시 HTTP 502 Bad Gateway 반환 및 상세 에러 은닉 (`test_provider_error_returns_502_...`).
   - 빈 답변(`empty`) 또는 비정상 구조(`malformed`) 수신 시 502 반환 및 미완성 대화 DB 미저장 확인.
3. 보안 및 개인정보 감사:
   - API 키 및 질문/답변 본문이 서버 로그(`app.log`)나 클라이언트 에러 응답에 노출되지 않는지 확인 (`test_logs_do_not_contain_key_or_message_bodies`).
4. 장애 복구력 (Fault Recovery):
   - 일시적 장애(502/504) 발생 후 다음 요청 시 정상적으로 복구되어 처리되는지 확인.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PASSWORD = "an example password"


class _GatewayHandler(BaseHTTPRequestHandler):
    """테스트 시나리오별로 다양한 HTTP 응답(성공, 지연, 에러, 기형 페이로드)을 모의하는 핸들러 클래스."""

    def do_POST(self):
        """클라이언트의 Chat Completions POST 요청을 수신하여 기록하고 모의 응답을 반환합니다."""
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")

        server = self.server
        # 테스트 검증을 위해 수신된 요청의 경로, 헤더, 본문을 기록
        server.requests.append(
            {"path": self.path, "authorization": self.headers.get("Authorization"), "body": body}
        )

        behaviour = server.behaviour
        if behaviour == "slow":
            # 타임아웃 테스트: 클라이언트 타임아웃보다 오래 대기하여 시간 초과 유발
            server.release.wait(timeout=10)
            return

        if behaviour == "error":
            # 공급자 오류 테스트: 401 Unauthorized 및 가상 API 키가 포함된 에러 응답
            payload = {"error": {"message": "invalid api key sk-secret-should-not-leak"}}
            raw = json.dumps(payload).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        # 정상 응답 모의
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
            raw = b'{"choices":'  # 깨진 JSON 데이터 전송
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        """테스트 콘솔 출력에 불필요한 기본 HTTP 접근 로그 출력을 억제합니다."""


@pytest.fixture
def gateway():
    """모의 AI 게이트웨이 HTTP 서버를 백그라운드 스레드에서 구동하는 픽스처.

    Yields:
        ThreadingHTTPServer: 가상 게이트웨이 서버 인스턴스 (base_url 포함)
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _GatewayHandler)
    server.requests = []
    server.behaviour = "ok"
    server.release = threading.Event()
    # shutdown() 응답성을 위해 poll_interval을 0.01초로 짧게 설정
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
    """llm_connect 모듈이 테스트용 모의 게이트웨이를 바라보도록 클라이언트를 교체하는 픽스처.

    [기술 설명]
    모듈을 reload하면 예외 클래스가 새 객체로 재생성되어 llm.py의 except 절이
    더 이상 같은 클래스를 잡지 못하는 문제가 발생하므로, 모듈 객체를 유지한 채
    `_client`, `AI_MODEL`, `AI_TIMEOUT` 속성만 monkeypatch로 안전하게 변경합니다.
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
    """채팅 테스트를 위한 인증된 사용자를 생성하고 로그인하는 픽스처."""
    credentials = {"username": "ai_user", "password": PASSWORD}
    assert client.post("/api/signup", json=credentials).status_code == 201
    assert client.post("/api/login", json=credentials).status_code == 200


def test_request_uses_openai_chat_completions_format(client, logged_in, connect, gateway):
    """요청이 OpenAI Chat Completions 포맷(엔드포인트, Authorization, 모델, 메시지)을 준수하는지 검증합니다."""
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
    """과거 대화 기록이 새 질문보다 앞선 순서로 메시지 배열에 구성되는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "질문 1"}).status_code == 200
    assert client.post("/api/chat", json={"question": "질문 2"}).status_code == 200

    assert gateway.requests[1]["body"]["messages"] == [
        {"role": "user", "content": "질문 1"},
        {"role": "assistant", "content": "게이트웨이 답변"},
        {"role": "user", "content": "질문 2"},
    ]


def test_question_is_not_duplicated_in_messages(client, logged_in, connect, gateway):
    """전송된 메시지 목록 내에서 현재 질문이 중복되어 덧붙여지지 않는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "중복 확인"}).status_code == 200

    contents = [message["content"] for message in gateway.requests[0]["body"]["messages"]]
    assert contents.count("중복 확인") == 1


def test_timeout_returns_504_and_does_not_save(client, logged_in, connect, gateway, caplog):
    """AI 응답 지연(타임아웃) 시 504 상태 코드가 반환되고 DB에 질문이 저장되지 않는지 검증합니다."""
    gateway.behaviour = "slow"

    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "느린 질문"})

    assert response.status_code == 504
    assert "지연" in response.json()["detail"]
    assert client.get("/api/me/chats").json() == []
    assert any("ai_call_timeout" in record.message for record in caplog.records)


def test_provider_error_returns_502_and_hides_details(client, logged_in, connect, gateway, caplog):
    """외부 AI 게이트웨이 오류 발생 시 502 상태 코드가 반환되고 API 키/세부 정보가 은닉되는지 검증합니다."""
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
    """AI가 빈 답변을 반환한 경우 비정상 응답(502)으로 처리되고 DB에 저장되지 않는지 검증합니다."""
    gateway.behaviour = "empty"

    assert client.post("/api/chat", json={"question": "빈 답변"}).status_code == 502
    assert client.get("/api/me/chats").json() == []


def test_successful_answer_is_saved_and_listed(client, logged_in, connect, gateway):
    """AI 대화 성공 시 질문과 답변이 DB에 저장되어 대화 기록 목록에서 확인되는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "저장될 질문"}).status_code == 200

    chats = client.get("/api/me/chats").json()
    assert [(chat["question"], chat["answer"]) for chat in chats] == [
        ("저장될 질문", "게이트웨이 답변")
    ]


def test_logs_do_not_contain_key_or_message_bodies(client, logged_in, connect, gateway, caplog):
    """AI 통신 로그에 인증 키 및 질문/답변 본문 내용이 남지 않는지 검증합니다."""
    with caplog.at_level(logging.INFO):
        assert client.post("/api/chat", json={"question": "비밀 질문"}).status_code == 200

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "ai_call_started" in logged
    assert "ai_call_success" in logged
    assert "test-gateway-key" not in logged
    assert "비밀 질문" not in logged
    assert "게이트웨이 답변" not in logged


def test_unauthenticated_request_does_not_call_gateway(client, connect, gateway):
    """비로그인 상태의 질문 요청 시 외부 게이트웨이로 네트워크 요청이 전달되지 않는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "비로그인"}).status_code == 401
    assert gateway.requests == []


def test_invalid_question_does_not_call_gateway(client, logged_in, connect, gateway):
    """질문 본문 유효성 검사(422) 실패 시 외부 게이트웨이를 호출하지 않는지 검증합니다."""
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422
    assert gateway.requests == []


def test_server_recovers_after_failed_call(client, logged_in, connect, gateway):
    """일시적 AI 통신 실패 후 다음 호출 시 서버가 정상적으로 복구되어 응답하는지 검증합니다."""
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
    """기형적인 JSON 응답(choices 부재, content 타입 불일치 등) 수신 시 안전하게 502로 처리되고 복구되는지 검증합니다."""
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
    """게이트웨이가 잘못된 형식의 원시 바이트(비정상 JSON)를 반환할 때 안전하게 502로 처리되는지 검증합니다."""
    gateway.behaviour = "invalid_json"
    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "형식 오류"})
    assert response.status_code == 502
    assert "ai_call_failure" in caplog.text
    assert client.get("/api/me/chats").json() == []
