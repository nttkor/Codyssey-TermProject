"""B 담당: 외부 AI 서비스와의 통신.

OpenAI 호환 게이트웨이에 Chat Completions 형식으로 요청한다.
제공자·모델·타임아웃은 `config.py`의 환경변수로 받는다.

llm.py와의 연결
- 인증·입력 검증·DB 문맥 조회·대화 저장은 llm.py에서 처리한다.
- 전달받은 history 뒤에 이번 question을 한 번 추가해 AI 요청을 구성한다.
- 성공하면 답변 문자열을 반환하고, 타임아웃은 AITimeoutError,
  그 밖의 통신 실패는 AIServiceError로 구분해 전달한다.
- HTTP 응답은 llm.py에서 만든다. 제공자의 오류 상세나 키는 사용자 응답에 노출하지 않는다.
"""

import time
from json import JSONDecodeError

from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_TIMEOUT
from app.logger import logger


class AIError(Exception):
    """외부 AI 통신 실패의 공통 상위 예외."""


class AITimeoutError(AIError):
    """AI_TIMEOUT 안에 답변을 받지 못했다."""


class AIServiceError(AIError):
    """제공자 오류, 연결 실패, 빈 응답 등 타임아웃이 아닌 실패."""


# 요청마다 TCP/TLS 연결과 커넥션 풀을 새로 만들지 않도록 비동기 클라이언트를
# 모듈 수준에서 재사용한다. 자동 재시도는 중복 질문 가능성을 피하기 위해 끈다.
# 재시도 여부는 502/504를 받은 화면에서 사용자가 결정한다.
_client = AsyncOpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL,
    timeout=AI_TIMEOUT,
    max_retries=0,
)


def _build_messages(question: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    """오래된 순서의 문맥 뒤에 이번 질문을 한 번만 덧붙인다."""
    # 호출자가 전달한 목록을 변경하지 않도록 새 목록을 만든다.
    return [*history, {"role": "user", "content": question}]


async def generate_answer(question: str, history: list[dict[str, str]]) -> str:
    """history는 오래된 순서의 role/content 메시지 목록, 반환값은 AI 답변 문자열."""
    messages = _build_messages(question, history)

    # 질문·답변 본문과 키는 기록하지 않는다. 추적에 필요한 값만 남긴다.
    logger.info(
        "ai_call_started model=%s message_count=%s timeout=%s",
        AI_MODEL,
        len(messages),
        AI_TIMEOUT,
    )
    started_at = time.monotonic()

    try:
        # base_url 뒤의 /chat/completions 호출과 Authorization 헤더 구성은 SDK가 담당한다.
        completion = await _client.chat.completions.create(
            model=AI_MODEL,
            messages=messages,
        )
    except APITimeoutError:
        # 시간 초과는 일시적인 지연으로 보고 라우터가 HTTP 504로 구분할 수 있게 전달한다.
        logger.warning(
            "ai_call_timeout model=%s elapsed=%.3f", AI_MODEL, time.monotonic() - started_at
        )
        raise AITimeoutError("AI 응답이 제한 시간을 초과했습니다.") from None
    except (OpenAIError, JSONDecodeError) as error:
        # 연결 실패, 인증 실패, 제공자 4xx/5xx 등 SDK 계열 오류는 HTTP 502 대상으로 묶는다.
        # 제공자 응답 본문에는 키나 내부 정보가 섞일 수 있으므로 예외 종류만 남긴다.
        logger.warning(
            "ai_call_failure model=%s elapsed=%.3f error_type=%s",
            AI_MODEL,
            time.monotonic() - started_at,
            type(error).__name__,
        )
        raise AIServiceError("AI 호출에 실패했습니다.") from None

    elapsed = time.monotonic() - started_at

    # HTTP 200이어도 choices가 없거나 content가 공백이면 정상 답변으로 저장하지 않는다.
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
        logger.warning("ai_call_failure model=%s elapsed=%.3f error_type=EmptyAnswer", AI_MODEL, elapsed)
        raise AIServiceError("AI가 빈 답변을 반환했습니다.")

    logger.info(
        "ai_call_success model=%s elapsed=%.3f answer_length=%s", AI_MODEL, elapsed, len(answer)
    )
    return answer
