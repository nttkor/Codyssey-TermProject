"""
AskMate 대화 기록 조회 라우터 (Chat History Router)

파일명   : history.py
생성자   : Changhwan Kim
생성일   : 2026/09/14
업데이트 : 2026/09/20

[파일 개요]
본 모듈은 인증된 사용자가 자신이 과거에 질의응답한 대화 목록을 최신순으로 조회할 수 있는
RESTful API 엔드포인트(`/api/me/chats`)를 제공합니다.

[보안 및 기술적 고려사항]
1. 인가 및 IDOR(Insecure Direct Object Reference) 방지:
   - 클라이언트의 쿼리 스트링이나 요청 본문에 전달되는 `user_id`를 일체 신뢰하지 않으며,
     오직 세션에서 검증된 `user.id`만을 조회 조건으로 사용함으로써 타인의 대화 열람을 원천 차단합니다.
2. 시간대 표준화 (ISO 8601 UTC):
   - SQLite DB에 타임존 정보 없이 저장된 `created_at` 필드에 명시적으로 `UTC` 타임존을 부여(`replace(tzinfo=UTC)`)하여
     Pydantic 직렬화 시 표준 ISO 8601 포맷(예: `2026-09-20T03:00:00.123456Z`)으로 출력되도록 합니다.
     이를 통해 프론트엔드가 사용자의 현지 시간대로 안전하게 포맷팅할 수 있습니다.
3. 브라우저 캐시 제어 (`Cache-Control: no-store`):
   - 대화 내역에 포함된 개인 정보와 질문 내용을 보호하기 위해 브라우저와 프록시 캐시를 방지합니다.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.chat_db import get_chats_by_user
from app.db_connect import get_db
from app.logger import logger
from app.models.user import User

# 대화 기록 라우터 인스턴스
router = APIRouter()


# ==============================================================================
# Pydantic 응답 스키마
# ==============================================================================
class ChatResponse(BaseModel):
    """대화 기록 단건 응답 DTO.

    Attributes:
        id (int): 대화 기록 고유 ID
        question (str): 사용자의 질문 본문
        answer (str): AI의 답변 본문
        created_at (datetime): UTC 시간대가 명시된 생성 일시
    """
    id: int
    question: str
    answer: str
    created_at: datetime


# ==============================================================================
# API 엔드포인트 구현
# ==============================================================================
@router.get("/me/chats", response_model=list[ChatResponse])
def get_my_chats(
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ChatResponse]:
    """현재 로그인한 사용자의 모든 대화 기록을 최신순으로 조회하여 반환합니다.

    [기술 설명]
    1. `get_current_user` 의존성을 통해 로그인 여부를 확인합니다 (미인증 시 401 Unauthorized 반환).
    2. 데이터베이스 계층의 `get_chats_by_user`를 호출하여 세션 사용자(`user.id`)의 대화만 가져옵니다.
    3. SQLite에 나이브(naive) 상태로 저장된 `created_at` 컬럼에 `tzinfo=UTC`를 바인딩하여
       클라이언트(프론트엔드)에서 일관된 UTC 표준 문자열을 수신할 수 있도록 변환합니다.
    4. 대화 기록이 전혀 없는 신규 사용자의 경우 빈 배열(`[]`)을 정상 반환합니다.
    5. 응답 헤더에 `Cache-Control: no-store`를 지정하여 대화 내역의 캐싱을 금지합니다.

    Args:
        response (Response): 응답 헤더 조작을 위한 FastAPI Response 객체
        user (User): 세션 인증을 통과한 현재 로그인 사용자 엔티티
        db (Session): 요청 라이프사이클에 바인딩된 SQLAlchemy DB 세션

    Returns:
        list[ChatResponse]: 최신순으로 정렬된 사용자 본인의 대화 기록 DTO 목록

    Raises:
        HTTPException: 데이터베이스 조회 오류 발생 시 500 Internal Server Error
    """
    try:
        chats = get_chats_by_user(db, user.id)
    except SQLAlchemyError:
        logger.exception("db_read_failure operation=history user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="대화 기록을 불러오지 못했습니다.") from None

    # 개인 대화 내용 캐시 방지
    response.headers["Cache-Control"] = "no-store"

    # 나이브 datetime에 UTC 타임존 정보를 명시하여 ISO 8601 문자열('Z' 접미사)로 변환
    return [
        ChatResponse(
            id=chat.id,
            question=chat.question,
            answer=chat.answer,
            created_at=chat.created_at.replace(tzinfo=UTC),
        )
        for chat in chats
    ]
