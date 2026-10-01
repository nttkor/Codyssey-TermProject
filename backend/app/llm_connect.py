"""
AskMate 외부 AI 통신 및 연동 모듈 (External AI Service Integration - B 담당)

[파일 개요]
본 모듈은 OpenAI 호환 API 게이트웨이(Chat Completions API)와 비동기로 통신하여
사용자의 질문과 과거 대화 문맥을 전달하고 AI 생성 답변을 수신하는 연동 계층입니다.
모델 식별자, 엔드포인트 URL, 인증 키, 타임아웃 등의 설정은 `app.config`에서 주입받아 사용합니다.

[역할 분담 및 협업 구조 (B 담당)]
- `llm.py`와의 인터페이스 및 책임 분리:
  * 인증, 파라미터 유효성 검사, DB 문맥 조회 및 대화 저장은 `llm.py`에서 전담합니다.
  * 본 모듈은 OpenAI 메시지 배열을 완성하고 HTTP 네트워크 통신 및 에러 캡슐화를 전담합니다.
  * 네트워크 타임아웃은 `AITimeoutError`로, 그 외 게이트웨이 장애/파싱 오류는 `AIServiceError`로
    구분하여 상위 계층(`llm.py`)에 전달합니다.

[주요 기술 설명]
1. 비동기 커넥션 풀링 (`AsyncOpenAI` 모듈 레벨 재사용):
   - 요청마다 TCP 3-way 핸드셰이크 및 TLS 암호화 연결을 맺는 부하를 방지하기 위해
     싱글톤 형태의 비동기 HTTP 클라이언트를 모듈 로드 시 생성하여 전역 재사용합니다.
2. 클라이언트 측 자동 재시도 비활성화 (`max_retries=0`):
   - LLM 질의는 무거운 생성 비용이 수반되며, 자동 재시도 시 사용자 모르게 중복 질문이 발생하거나
     응답 지연이 배가될 수 있습니다. 실패(502/504) 시 재전송 여부는 UI 화면에서 사용자가 직접 결정합니다.
3. 정보 보안 및 감사 로그:
   - 개인정보 보호 및 보안 규정에 따라 질문/답변 본문과 API Key는 로그에 일체 남기지 않습니다.
   - 모델명, 메시지 개수, 타임아웃, 소요 시간(초 단위), 예외 클래스명 등 장애 분석에 필요한 메타데이터만 기록합니다.
4. 방어적 응답 검증 (Defensive Response Validation):
   - 게이트웨이가 HTTP 200을 반환하더라도 `choices` 필드가 비어있거나, `content`가 누락/비문자열이거나,
     공백 문자열만 존재하는 경우 비정상 응답으로 간주하여 `AIServiceError`를 발생시킵니다.
"""

import time
from json import JSONDecodeError

from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_TIMEOUT
from app.logger import logger


# ==============================================================================
# 커스텀 예외 클래스 계층 구조
# ==============================================================================
class AIError(Exception):
    """외부 AI 게이트웨이 통신 실패의 최상위 공통 예외 클래스."""


class AITimeoutError(AIError):
    """설정된 제한 시간(AI_TIMEOUT) 내에 AI 답변을 수신하지 못한 경우 발생하는 예외."""


class AIServiceError(AIError):
    """제공자 서버 장애, 4xx/5xx HTTP 오류, 연결 단절, 응답 형식 불일치 등 일반 통신 실패 예외."""


# ==============================================================================
# 비동기 OpenAI 클라이언트 인스턴스 (커넥션 풀 재사용)
# ==============================================================================
# 요청마다 TCP/TLS 연결과 커넥션 풀을 새로 만들지 않도록 비동기 클라이언트를
# 모듈 수준에서 재사용합니다. 자동 재시도는 중복 질문 가능성을 피하기 위해 비활성화(max_retries=0)합니다.
# 재시도 여부는 502/504 상태 코드를 받은 화면에서 사용자가 능동적으로 결정합니다.
_client = AsyncOpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,
    timeout=AI_TIMEOUT,
    max_retries=0,
)


def _build_messages(question: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    """과거 대화 내역 목록 뒤에 현재 질문을 user 역할로 결합한 새 메시지 목록을 생성합니다.

    [기술 설명]
    - 원본 `history` 리스트를 직접 수정(mutate)하지 않고 언패킹(`*history`)을 통해
      새로운 리스트를 생성함으로써 부수 효과(Side-effect)를 차단합니다.

    Args:
        question (str): 현재 전송할 사용자의 최신 질문
        history (list[dict[str, str]]): 과거 대화 메시지 딕셔너리 목록 (오래된 순)

    Returns:
        list[dict[str, str]]: Chat Completions 규격에 맞게 결합된 최종 메시지 리스트
    """
    # 호출자가 전달한 목록을 변경하지 않도록 불변성을 유지하는 새 리스트 생성
    return [*history, {"role": "user", "content": question}]


async def generate_answer(question: str, history: list[dict[str, str]]) -> str:
    """외부 AI API에 비동기 Chat Completion 요청을 전송하고 검증된 답변 텍스트를 반환합니다.

    [기술 설명]
    1. 메시지 배열 생성 및 소요 시간 측정을 위한 타이머(`time.monotonic()`)를 시작합니다.
    2. SDK의 `_client.chat.completions.create`를 호출하여 외부 게이트웨이와 통신합니다.
    3. 예외 처리:
       - `APITimeoutError`: 설정된 타임아웃 초과 시 `AITimeoutError`로 변환하여 라우터가 504로 응답하도록 유도.
       - `OpenAIError`, `JSONDecodeError`: 통신 두절, 4xx/5xx 응답 등은 `AIServiceError`로 변환하여 라우터가 502로 응답하도록 유도.
         (제공자 응답 본문에 API 키나 내부 시스템 정보가 포함될 수 있으므로 예외 클래스 이름만 로깅)
    4. 방어적 응답 검증:
       - choices 유무, message 객체 유무, content 타입 검사, 양끝 공백 제거 후 빈 문자열 여부를 확인하여
         온전한 답변이 확보되었을 때만 반환합니다.

    Args:
        question (str): 사용자가 입력한 현재 질문
        history (list[dict[str, str]]): 이전 대화 문맥 (오래된 순서의 user/assistant 메시지)

    Returns:
        str: 양끝 공백이 정리된 AI의 최종 답변 텍스트

    Raises:
        AITimeoutError: AI 게이트웨이 응답 제한 시간 초과 시 발생
        AIServiceError: AI 통신 실패, 제공자 오류, 또는 유효하지 않은 응답 형식인 경우 발생
    """
    messages = _build_messages(question, history)

    # 질문·답변 본문과 API 키는 보안을 위해 기록하지 않고, 모니터링 메타데이터만 기록합니다.
    logger.info(
        "ai_call_started model=%s message_count=%s timeout=%s",
        AI_MODEL,
        len(messages),
        AI_TIMEOUT,
    )
    started_at = time.monotonic()

    try:
        # base_url 뒤의 /chat/completions 호출과 Authorization 헤더 구성은 SDK가 담당합니다.
        completion = await _client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
        )
    except APITimeoutError:
        # 시간 초과는 일시적인 지연으로 보고 라우터가 HTTP 504로 구분할 수 있게 전달합니다.
        logger.warning(
            "ai_call_timeout model=%s elapsed=%.3f", AI_MODEL, time.monotonic() - started_at
        )
        raise AITimeoutError("AI 응답이 제한 시간을 초과했습니다.") from None
    except (OpenAIError, JSONDecodeError) as error:
        # 연결 실패, 인증 실패, 제공자 4xx/5xx 등 SDK 계열 오류는 HTTP 502 대상으로 묶습니다.
        # 제공자 응답 본문에는 키나 내부 정보가 섞일 수 있으므로 예외 종류만 남깁니다.
        logger.warning(
            "ai_call_failure model=%s elapsed=%.3f error_type=%s",
            AI_MODEL,
            time.monotonic() - started_at,
            type(error).__name__,
        )
        raise AIServiceError("AI 호출에 실패했습니다.") from None

    elapsed = time.monotonic() - started_at

    # HTTP 200이어도 choices가 없거나 content가 공백이면 정상 답변으로 저장하지 않습니다.
    choices = getattr(completion, "choices", None)
    message = getattr(choices[0], "message", None) if isinstance(choices, list) and choices else None
    content = getattr(message, "content", None)
    if not isinstance(content, str):
        logger.warning(
            "ai_call_failure model=%s elapsed=%.3f error_type=InvalidAnswer",
            AI_MODEL, elapsed,
        )
        raise AIServiceError("AI 응답 형식이 올바르지 않습니다.") from None

    answer = content.strip()
    if not answer:
        logger.warning(
            "ai_call_failure model=%s elapsed=%.3f error_type=EmptyAnswer",
            AI_MODEL, elapsed,
        )
        raise AIServiceError("AI가 빈 답변을 반환했습니다.")

    logger.info(
        "ai_call_success model=%s elapsed=%.3f answer_length=%s",
        AI_MODEL, elapsed, len(answer),
    )
    return answer
