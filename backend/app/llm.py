"""
AskMate AI 채팅 및 대화 오케스트레이션 라우터 (AI Chat Orchestration Router)

파일명   : llm.py
생성자   : Changhwan Kim
생성일   : 2026/09/14
업데이트 : 2026/09/25

[파일 개요]
본 모듈은 인증된 사용자의 질문을 수신하여 이전 대화 문맥(최근 5쌍)을 조회하고,
외부 AI 모델과 통신(`llm_connect.py`)하여 생성된 답변을 전달받은 뒤,
질문·답변 쌍을 데이터베이스에 영구 저장하는 전체 AI 채팅 워크플로를 오케스트레이션합니다.

[역할 분담 및 협업 구조]
- 팀원 A:
  * 인증 검증(`get_current_user`), CSRF 방어(`require_csrf_header`), 질문 글자 수 검증(1~1000자).
  * 최근 대화 문맥 조회 및 OpenAI 메시지 포맷(`user`/`assistant`) 평탄화 변환.
  * 이벤트 루프 블로킹 방지를 위한 `run_in_threadpool` 기반 동기 DB 작업 래핑.
  * 대화 기록 DB 저장(`create_chat`) 및 요청/DB 감사 로그 기록.
- 팀원 B:
  * `llm_connect.py`의 비동기 OpenAI API 통신 구현.
  * 외부 AI 통신 예외의 HTTP 상태 코드 매핑 (타임아웃은 504 Gateway Timeout, 일반 실패는 502 Bad Gateway).
  * 외부 서비스 에러 메시지 은닉 및 표준 사용자 안내 문구 반환.

[보안 및 기술적 고려사항]
1. 비동기 이벤트 루프 최적화 (`run_in_threadpool`):
   - SQLAlchemy의 동기식 SQLite 쿼리가 FastAPI의 단일 스레드 비동기 이벤트 루프(Event Loop)를
     블로킹(지연)하지 않도록 별도의 스레드 풀에서 실행합니다.
2. 예외 마스킹 및 보안 격리:
   - 외부 AI 게이트웨이의 API 키, 내부 URL, 세부 오류 스택이 클라이언트에 노출되지 않도록
     정의된 사용자 친화적 메시지만을 반환합니다.
3. 원자적 트랜잭션 보장:
   - AI 통신이 100% 성공하여 유효한 답변을 얻었을 때만 DB 저장을 진행하며,
     AI 호출 실패 시에는 미완성 레코드가 생성되지 않습니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import llm_connect
from app.auth import get_current_user, require_csrf_header
from app.llm_connect import AIServiceError, AITimeoutError
from app.chat_db import create_chat, get_recent_chats_by_user
from app.db_connect import get_db
from app.logger import logger
from app.models.user import User

# AI 대화 라우터 인스턴스
router = APIRouter()


# ==============================================================================
# Pydantic 요청 스키마
# ==============================================================================
class ChatRequest(BaseModel):
    """채팅 질문 전송 요청 본문 스키마.

    Attributes:
        question (str): 사용자 질문 내용 (앞뒤 공백 제거 후 1자 이상 1000자 이하).
    """
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]


# ==============================================================================
# API 엔드포인트 구현
# ==============================================================================
@router.post("/chat", dependencies=[Depends(require_csrf_header)])
async def chat(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """사용자의 질문을 받아 이전 대화 문맥과 함께 AI에 질의하고, 결과를 DB에 저장한 후 반환합니다.

    [기술 설명]
    1. 보안 검증:
       - `require_csrf_header`: 브라우저 기반 단순 요청 공격 방어
       - `get_current_user`: 세션 검증을 통과한 사용자만 접근 허용 (미인증 시 401)
    2. 최근 문맥 조회:
       - `get_recent_chats_by_user`를 `run_in_threadpool`로 호출하여 비동기 루프 정체 없이
         사용자의 직전 대화 최대 5쌍을 오래된 순서로 가져옵니다.
    3. OpenAI 메시지 규격 구성:
       - 과거의 질문/답변 쌍을 `[{"role": "user", ...}, {"role": "assistant", ...}]` 형태로 평탄화합니다.
    4. AI 통신 및 예외 처리 (B 담당):
       - `llm_connect.generate_answer`를 비동기 호출합니다.
       - 타임아웃 발생(`AITimeoutError`): 504 Gateway Timeout 반환
       - 통신/제공자 장애(`AIServiceError`): 502 Bad Gateway 반환
    5. 대화 쌍 DB 영구 저장:
       - AI가 정상 응답을 생성한 경우에 한해, 동기 `create_chat` 함수를 스레드 풀에서 실행하여 저장합니다.

    Args:
        payload (ChatRequest): 유효성 검사를 통과한 사용자 질문 객체
        user (User): 인증된 현재 로그인 사용자 객체
        db (Session): 요청 라이프사이클에 바인딩된 DB 세션

    Returns:
        dict[str, str]: AI가 생성한 최종 답변 본문 `{"answer": str}`

    Raises:
        HTTPException:
            - 401: 비로그인 상태
            - 403: CSRF 검증 실패
            - 422: 질문 길이 제한(1~1000자) 위반
            - 500: 데이터베이스 읽기 또는 저장 실패
            - 502: 외부 AI 서비스 연동 실패
            - 504: AI 서비스 응답 시간 초과
    """
    user_id = user.id
    logger.info("request_received user_id=%s path=/api/chat", user_id)

    # 1단계: 최근 대화 문맥 조회 (동기 DB I/O를 스레드 풀에 위임)
    try:
        chats = await run_in_threadpool(get_recent_chats_by_user, db, user_id)
    except SQLAlchemyError:
        logger.exception("db_read_failure operation=chat_context user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="최근 대화 기록을 불러오지 못했습니다.") from None

    # 2단계: B의 AI 통신 모듈이 바로 사용할 수 있도록 대화 기록을 OpenAI messages 리스트로 구성
    # DB 조회 결과는 이미 오래된 순(오름차순)으로 정렬되어 전달됩니다.
    history: list[dict[str, str]] = []
    for chat in chats:
        history.extend([
            {"role": "user", "content": chat.question},
            {"role": "assistant", "content": chat.answer},
        ])

    # 3단계: 외부 AI 서비스 호출 및 상태 코드 매핑 (B 담당)
    # 공급자의 상세 오류 메시지나 API 키가 유출되지 않도록 표준화된 안내 메시지만 클라이언트에 전달합니다.
    try:
        answer = await llm_connect.generate_answer(payload.question, history=history)
    except AITimeoutError:
        logger.warning("ai_failure operation=chat user_id=%s reason=timeout", user_id)
        raise HTTPException(
            status_code=504, detail="AI 응답이 지연되어 답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요."
        ) from None
    except AIServiceError:
        logger.warning("ai_failure operation=chat user_id=%s reason=service", user_id)
        raise HTTPException(
            status_code=502, detail="AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."
        ) from None

    # 4단계: 정상 답변 수신 완료 시 질문·답변 한 쌍을 DB에 저장
    try:
        chat_id = await run_in_threadpool(create_chat, db, user_id, payload.question, answer)
    except SQLAlchemyError:
        logger.exception("db_save_failure operation=chat user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="대화 기록을 저장하지 못했습니다.") from None

    logger.info("db_save_success operation=chat user_id=%s chat_id=%s", user_id, chat_id)
    return {"answer": answer}
