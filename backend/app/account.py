"""
AskMate 사용자 계정 및 인증 라우터 (Account & Authentication Router)

파일명   : account.py
생성자   : Changhwan Kim
생성일   : 2026/09/14
업데이트 : 2026/09/20

[파일 개요]
본 모듈은 회원가입(`/api/signup`), 로그인(`/api/login`), 현재 사용자 정보 조회(`/api/me`),
그리고 로그아웃(`/api/logout`) 등 사용자 라이프사이클과 인증에 관련된 핵심 RESTful API를 제공합니다.

[보안 및 기술적 고려사항]
1. 입력 데이터 정규화 및 비밀번호 보호:
   - `Username`: PEP 695 타입 별칭을 사용하며, 공백 제거(`strip_whitespace`), 영문 소문자 통일(`to_lower`),
     정규식(영문자/숫자/밑줄만 허용)을 적용하여 대소문자 혼동으로 인한 다중 가입 문제를 방지합니다.
   - `SecretStr`: Pydantic의 `SecretStr` 타입을 사용하여 메모리 덤프, 로그 출력, 문자열 변환 시
     비밀번호 평문이 노출되지 않고 `**********`로 마스킹되도록 보호합니다.
2. 세션 고정(Session Fixation) 공격 방어:
   - 로그인 성공 시 기존 세션 데이터를 완전히 비우는 `request.session.clear()`를 호출한 뒤
     새로운 `user_id`를 할당하여 세션 하이재킹을 방지합니다.
3. 브라우저 캐시 방지 (`Cache-Control: no-store`):
   - 개인정보가 포함된 로그인, 내 정보 조회, 로그아웃 응답에 캐시 방지 헤더를 명시하여
     공용 PC나 브라우저 뒤로 가기 시 사용자 정보가 노출되지 않도록 조치합니다.
4. 중복 가입 처리:
   - 애플리케이션 레벨의 선행 조회에 의존하지 않고, SQLite의 UNIQUE 제약조건 위반 에러코드
     (`SQLITE_CONSTRAINT_UNIQUE`)를 직접 감지하여 HTTP 409 Conflict로 변환함으로써
     동시 요청 시의 경쟁 상태(Race Condition)를 안전하게 해결합니다.
"""

from sqlite3 import SQLITE_CONSTRAINT_UNIQUE
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr, StringConstraints
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.account_db import create_user, get_user_by_username
from app.auth import get_current_user, require_csrf_header
from app.db_connect import get_db
from app.logger import logger
from app.models.user import User
from app.security import hash_password, verify_password

# 계정 관리 API 라우터 인스턴스
router = APIRouter()


# ==============================================================================
# Pydantic 타입 및 DTO 스키마 정의
# ==============================================================================
# 사용자명 유효성 검사 규칙 (3~30자의 영문 대소문자, 숫자, 밑줄 허용 및 소문자 정규화)
type Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=30,
        pattern=r"^[a-zA-Z0-9_]+$",
    ),
]


class SignUpPayload(BaseModel):
    """회원가입 요청 본문 스키마."""
    username: Username
    # 비밀번호 최소 8자 이상, 최대 128자 이하의 강력한 비밀번호 정책 적용
    password: Annotated[SecretStr, Field(min_length=8, max_length=128)]


class LoginPayload(BaseModel):
    """로그인 요청 본문 스키마."""
    username: Username
    # 가입 시의 정책 변경과 무관하게 과거 가입자의 로그인을 허용할 수 있도록 최소 1자로 완화하며,
    # 비밀번호에 포함된 의도적 공백이 훼손되지 않도록 strip을 수행하지 않습니다.
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class UserResponse(BaseModel):
    """사용자 정보 응답 DTO (비밀번호 해시 등의 민감 정보 제외)."""
    id: int
    username: str


# ==============================================================================
# API 엔드포인트 구현
# ==============================================================================
@router.post(
    "/signup", status_code=201, response_model=UserResponse,
    dependencies=[Depends(require_csrf_header)],
)
def signup(payload: SignUpPayload, db: Annotated[Session, Depends(get_db)]) -> UserResponse:
    """새로운 사용자를 등록(회원가입)합니다.

    [기술 설명]
    1. CSRF 공격을 방지하기 위해 `require_csrf_header` 의존성을 필수 요구합니다.
    2. 평문 비밀번호를 Argon2id로 단방향 암호화(`hash_password`)합니다.
    3. `create_user`를 통해 DB에 계정을 생성합니다.
    4. 이미 존재하는 사용자명인 경우 DB 레벨의 UNIQUE 제약조건 위반(SQLITE_CONSTRAINT_UNIQUE)을
       감지하여 409 Conflict 에러를 반환합니다.
    5. 보안 모범 사례에 따라 회원가입 직후 자동으로 로그인 세션을 발급하지 않고,
       201 Created 응답 후 클라이언트가 명시적으로 로그인을 거치도록 유도합니다.

    Args:
        payload (SignUpPayload): 사용자명과 비밀번호를 담은 요청 본문
        db (Session): SQLAlchemy 데이터베이스 세션

    Returns:
        UserResponse: 생성된 사용자의 ID와 정규화된 사용자명

    Raises:
        HTTPException: 사용자명 중복(409) 또는 DB 저장 실패(500) 시 발생
    """
    logger.info("request_received path=/api/signup")
    password_hash = hash_password(payload.password.get_secret_value())
    try:
        user_id = create_user(db, payload.username, password_hash)
    except SQLAlchemyError as exc:
        # SQLite 고유 제약조건 위반 에러 검사 (동시 가입 경쟁 상태 방어)
        if (
            isinstance(exc, IntegrityError)
            and exc.orig.sqlite_errorcode == SQLITE_CONSTRAINT_UNIQUE
        ):
            logger.warning("signup_duplicate_username")
            raise HTTPException(status_code=409, detail="이미 사용 중인 사용자명입니다.") from None
        logger.exception("db_save_failure operation=signup")
        raise HTTPException(status_code=500, detail="회원가입 정보를 저장하지 못했습니다.") from None

    logger.info("db_save_success operation=signup user_id=%s", user_id)
    return UserResponse(id=user_id, username=payload.username)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(require_csrf_header)])
def login(
    payload: LoginPayload,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """사용자 자격 증명을 검증하고 암호화된 세션 쿠키를 발급합니다.

    [기술 설명]
    1. 사용자명으로 사용자를 조회하고, `verify_password`를 통해 상수 시간 비밀번호 검증을 수행합니다.
    2. 존재하지 않는 사용자이거나 비밀번호가 틀린 경우, 공격자가 아이디 존재 여부를 유추할 수 없도록
       동일하게 "사용자명 또는 비밀번호가 올바르지 않습니다."(401 Unauthorized)로 일괄 응답합니다.
    3. 세션 고정 공격 방어를 위해 기존 세션을 비운(`request.session.clear()`) 뒤,
       현재 사용자의 `user_id`를 새로 주입합니다.
    4. 민감한 세션 응답이 프록시나 브라우저 캐시에 남지 않도록 `Cache-Control: no-store` 헤더를 설정합니다.

    Args:
        payload (LoginPayload): 로그인 아이디와 패스워드
        request (Request): 세션 관리를 위한 요청 객체
        response (Response): 응답 헤더 제어를 위한 응답 객체
        db (Session): SQLAlchemy 데이터베이스 세션

    Returns:
        UserResponse: 로그인에 성공한 사용자의 ID 및 계정명

    Raises:
        HTTPException: 인증 실패(401) 또는 DB 조회 실패(500) 시 발생
    """
    logger.info("request_received path=/api/login")
    try:
        user = get_user_by_username(db, payload.username)
    except SQLAlchemyError:
        logger.exception("db_read_failure operation=login")
        raise HTTPException(status_code=500, detail="로그인 정보를 확인하지 못했습니다.") from None

    # 사용자 부재 또는 비밀번호 불일치 검증
    if user is None or not verify_password(payload.password.get_secret_value(), user.password_hash):
        logger.warning("login_failure")
        raise HTTPException(status_code=401, detail="사용자명 또는 비밀번호가 올바르지 않습니다.")

    # 세션 고정(Session Fixation) 공격 방지를 위한 세션 재생성
    request.session.clear()
    request.session["user_id"] = user.id
    response.headers["Cache-Control"] = "no-store"
    logger.info("login_success user_id=%s", user.id)
    return UserResponse(id=user.id, username=user.username)


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """현재 세션으로 로그인된 사용자의 공개 계정 정보를 조회합니다.

    [기술 설명]
    - `get_current_user` 의존성을 통해 비인가 사용자를 사전에 차단(401)합니다.
    - 개인 프로필 정보가 브라우저나 중간 프록시에 캐싱되지 않도록 `no-store`를 명시합니다.

    Args:
        response (Response): 응답 헤더 설정을 위한 응답 객체
        user (User): 세션 인증을 통과한 현재 로그인 사용자 객체

    Returns:
        UserResponse: 로그인한 사용자의 고유 ID 및 사용자명
    """
    response.headers["Cache-Control"] = "no-store"
    return UserResponse(id=user.id, username=user.username)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
def logout(request: Request) -> Response:
    """현재 브라우저에 할당된 로그인 세션을 안전하게 초기화(로그아웃)합니다.

    [기술 설명]
    1. CSRF 방지 헤더를 확인합니다.
    2. `request.session.clear()`를 호출하여 서버 측 세션 데이터를 비우고,
       응답 시 클라이언트의 쿠키를 만료(Expires=1970)시키는 Set-Cookie 헤더를 전송합니다.
    3. 이미 비로그인 상태이거나 세션이 만료된 상태에서 호출하더라도 에러 없이 멱등하게 204 No Content를 반환합니다.

    Args:
        request (Request): 세션을 소유한 HTTP 요청 객체

    Returns:
        Response: 상태 코드 204 및 캐시 방지 헤더를 포함한 빈 응답
    """
    logger.info("request_received path=/api/logout")
    user_id = request.session.get("user_id")
    request.session.clear()
    logger.info("logout_success user_id=%s", user_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
