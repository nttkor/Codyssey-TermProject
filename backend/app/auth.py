"""
AskMate 인증 및 보안 종속성 모듈 (Authentication & Security Dependencies)

[파일 개요]
본 모듈은 FastAPI 의존성 주입(Dependency Injection) 시스템을 활용하여
클라이언트의 세션 인증 상태를 확인하고, 크로스 사이트 요청 위조(CSRF) 공격을 방어하는
공통 보안 가드 함수들을 제공합니다.

[보안 아키텍처 및 기술 설명]
1. CSRF 방어 매커니즘 (`require_csrf_header`):
   - 브라우저의 기본 HTML `<form>` 전송이나 이미지/스크립트 태그를 이용한 단순 요청(Simple Request)은
     커스텀 HTTP 헤더를 임의로 추가할 수 없습니다.
   - 모든 상태 변경(POST) 요청에 `X-Requested-With: XMLHttpRequest` 커스텀 헤더를 강제함으로써,
     공격자의 외부 도메인에서 희생자의 세션 쿠키를 이용해 악의적인 API 호출을 유도하는 CSRF를 원천 차단합니다.
   - 단, 이 방식은 교차 출처 리소스 공유(CORS)를 허용하지 않는 단일 출처(Same-origin) 서비스 전제하에 유효합니다.
2. 계층형 세션 사용자 확인:
   - `get_session_user`: 세션 쿠키에서 `user_id`를 추출하고 DB에서 사용자 엔티티를 조회합니다.
     비로그인 상태나 페이지 접근 제어 분기(로그인 페이지 리다이렉트 등)를 위해 비로그인 시 `None`을 반환합니다.
   - `get_current_user`: 반드시 로그인이 필요한 보호된 API 엔드포인트에서 사용되며,
     비로그인 상태인 경우 즉시 HTTP 401 Unauthorized 예외를 발생시킵니다.
   - 고스트 세션 자동 정리: 세션에는 `user_id`가 있으나 DB에서 해당 계정이 이미 삭제된 경우,
     `request.session.clear()`를 수행하여 유효하지 않은 세션을 즉각 무효화합니다.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.account_db import get_user_by_id
from app.db_connect import get_db
from app.logger import logger
from app.models.user import User


def require_csrf_header(
    requested_with: Annotated[
        str | None,
        Header(alias="X-Requested-With", description="POST 요청에는 XMLHttpRequest를 지정합니다."),
    ] = None,
) -> None:
    """CSRF(Cross-Site Request Forgery) 방어를 위해 요청 헤더의 X-Requested-With 값을 검증합니다.

    [보안 기술 설명]
    - 브라우저는 자바스크립트(fetch, XMLHttpRequest)를 통해서만 커스텀 헤더를 설정할 수 있습니다.
    - 서드파티 악성 사이트의 HTML 폼이나 태그를 통한 크로스 사이트 단순 요청(Simple Request)에는
      이 헤더가 포함될 수 없으므로, 헤더 존재 여부만으로 CSRF 공격을 효과적으로 방어할 수 있습니다.
    - CORS가 비활성화된 동일 출처 환경에서 간결하고 강력한 보호 수단을 제공합니다.

    Args:
        requested_with (str | None): HTTP 요청 헤더의 'X-Requested-With' 값

    Raises:
        HTTPException: 헤더가 누락되었거나 'XMLHttpRequest'가 아닌 경우 403 Forbidden 발생
    """
    if requested_with != "XMLHttpRequest":
        raise HTTPException(status_code=403, detail="X-Requested-With: XMLHttpRequest 헤더가 필요합니다.")


def get_session_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    """현재 요청의 쿠키 세션에서 사용자 식별자를 읽어 DB의 User 객체를 반환합니다.

    [기술 설명]
    1. `request.session`에서 `user_id`를 조회합니다. 키가 없으면 미인증 상태로 간주하고 `None`을 반환합니다.
    2. `user_id`가 존재하면 DB 조회를 수행합니다.
    3. 만약 DB에서 사용자를 찾을 수 없는 경우(예: 탈퇴/삭제된 계정), 세션을 클리어(`clear()`)하여
       오래된 세션 쿠키를 무효화하고 `None`을 반환합니다.
    4. DB 조회 중 데이터베이스 장애가 발생하면 500 오류를 발생시킵니다.

    Args:
        request (Request): Starlette/FastAPI HTTP 요청 객체
        db (Session): 의존성 주입을 통해 전달받은 DB 세션

    Returns:
        User | None: 인증된 사용자 엔티티 또는 미인증 시 None

    Raises:
        HTTPException: DB 연결 또는 쿼리 실패 시 500 Internal Server Error 발생
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        user = get_user_by_id(db, user_id)
    except SQLAlchemyError:
        logger.exception("db_read_failure operation=session")
        raise HTTPException(status_code=500, detail="로그인 정보를 확인하지 못했습니다.") from None
    if user is None:
        # DB에 사용자가 존재하지 않는데 세션만 남아있는 고스트 세션 상태 정리
        request.session.clear()
    return user


def get_current_user(user: Annotated[User | None, Depends(get_session_user)]) -> User:
    """로그인이 필수적인 보호된 API 엔드포인트에서 호출하는 엄격한 인증 의존성 함수입니다.

    [기술 설명]
    - `get_session_user`를 상위 의존성으로 호출한 뒤, 반환된 객체가 `None`이면
      즉시 HTTP 401 Unauthorized 에러를 발생시켜 비인가 접근을 차단합니다.

    Args:
        user (User | None): get_session_user 의존성으로부터 전달받은 사용자 객체

    Returns:
        User: 인증이 확인된 사용자 엔티티 객체

    Raises:
        HTTPException: 비로그인 상태일 때 401 Unauthorized ("로그인이 필요합니다.") 발생
    """
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user
