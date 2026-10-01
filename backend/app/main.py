"""
AskMate FastAPI 메인 애플리케이션 진입점 (Application Entrypoint)

파일명   : main.py
생성자   : Changhwan Kim
생성일   : 2026/09/14
업데이트 : 2026/09/20

[파일 개요]
본 모듈은 AskMate 백엔드의 최상위 진입점(Entrypoint)으로서 FastAPI 인스턴스를 생성하고,
서버 생명주기(Lifespan) 이벤트 처리, 보안 세션 미들웨어 등록, 정적 파일 마운트,
그리고 기능별 하위 라우터(계정, 대화 기록, AI 채팅, HTML 페이지)를 통합 조립합니다.
또한 유효성 검사 실패 시 발생할 수 있는 민감 정보 노출을 방지하기 위한 전역 예외 처리기를 등록합니다.

[주요 아키텍처 및 기술 설명]
1. Lifespan 비동기 컨텍스트 매니저:
   - FastAPI 0.93+ 권장 표준인 `lifespan` 매커니즘을 적용하여 기동 시 DB 테이블 자동 생성(`init_db()`)을
     수행하고, 서버 종료 시 커넥션 풀을 안전하게 해제(`engine.dispose()`)하여 리소스 누수를 방지합니다.
2. 암호화 서명 세션 미들웨어 (`SessionMiddleware`):
   - 클라이언트의 쿠키에 상태를 저장하되, 서버의 비밀키(`SESSION_SECRET_KEY`)로 변조 방지 서명을 수행합니다.
   - `same_site="lax"` 설정을 통해 제3자 사이트에서의 크로스 사이트 요청 전송(CSRF)을 방어합니다.
   - `https_only`: 배포 환경에서 HTTPS가 아닌 평문 HTTP 요청에는 쿠키를 전송하지 않도록 강제합니다.
3. 입력 검증 예외 마스킹 (`RequestValidationError` 핸들러):
   - FastAPI/Pydantic의 기본 422 응답은 실패한 입력값(`input`)을 그대로 에코(반사)합니다.
   - 비밀번호 입력 오류 시 평문 비밀번호가 응답 본문에 노출되는 중대한 보안 결함을 차단하기 위해,
     `type`, `loc`, `msg`만 선별하여 응답하도록 필터링합니다.
4. 모듈식 라우팅 구조:
   - 프론트엔드 HTML 렌더링 라우터(`pages_router`)와 REST API 라우터(`account`, `llm`, `history`)를
     명확히 분리하고 API에는 `/api` 접두사를 일관되게 부여합니다.
"""

# 파이썬 표준 및 서드파티 라이브러리
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# 자체 제작 코어 모듈
from app.logger import logger
from app.config import APP_DIR, SESSION_HTTPS_ONLY, SESSION_MAX_AGE, SESSION_SECRET_KEY
from app.db_connect import engine, init_db

# 기능별 라우터 모듈
from app.account import router as account_router
from app.history import router as history_router
from app.llm import router as llm_router
from app.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 애플리케이션의 시작(Startup) 및 종료(Shutdown) 생명주기를 관리합니다.

    [기술 설명]
    - 시작 단계:
      1. `init_db()`를 호출하여 DB 연결을 점검하고 누락된 테이블 스키마를 초기화합니다.
      2. 서버 시작 시각을 로그에 기록하여 기동 상태를 알립니다.
    - 실행 단계:
      - `yield` 구문을 통해 제어권을 넘겨 애플리케이션이 클라이언트 요청을 수신할 수 있게 합니다.
    - 종료 단계:
      - `finally` 블록에서 `engine.dispose()`를 호출하여 열려 있는 모든 DB 연결 풀을 안전하게 닫습니다.

    Args:
        app (FastAPI): 현재 실행 중인 FastAPI 애플리케이션 인스턴스
    """
    init_db()
    server_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("------------------------------------------------------------")
    logger.info(f"AskMate Backend Server started at {server_start_time}")
    logger.info("------------------------------------------------------------")
    try:
        yield
    finally:
        engine.dispose()


# ==============================================================================
# FastAPI 애플리케이션 인스턴스 생성 및 설정
# ==============================================================================
app = FastAPI(title="AskMate", lifespan=lifespan)

# 쿠키 기반 세션 미들웨어 등록
# 클라이언트에 전달되는 askmate_session 쿠키의 암호화 서명, 유효 기간, 보안 속성을 정의합니다.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="askmate_session",
    max_age=SESSION_MAX_AGE,
    same_site="lax",                 # CSRF 공격 완화를 위한 SameSite Lax 정책
    https_only=SESSION_HTTPS_ONLY,   # 운영 배포 시 HTTPS 전용 전송(Secure 플래그)
)

# 정적 파일 서빙 등록 (/static 경로를 통해 css, js, 이미지 파일 제공)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# ==============================================================================
# 라우터 등록 (Router Registration)
# ==============================================================================
# HTML 페이지 렌더링 라우터 (루트, 로그인, 회원가입, 채팅, 히스토리 화면)
app.include_router(pages_router)

# 비즈니스 로직 REST API 라우터 등록 (/api 접두사 적용)
app.include_router(account_router, prefix="/api")  # 회원가입, 로그인, 로그아웃, 내 정보
app.include_router(llm_router, prefix="/api")      # AI 대화 요청
app.include_router(history_router, prefix="/api")  # 대화 기록 조회


# ==============================================================================
# 전역 예외 처리기 (Global Exception Handlers)
# ==============================================================================
@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """Pydantic 요청 데이터 유효성 검사 실패 시 호출되는 커스텀 예외 핸들러입니다.

    [보안적 기술 설명]
    - 기본 FastAPI 422 응답에는 검증에 실패한 원래 입력값(`input`)이 그대로 포함됩니다.
    - 만약 비밀번호 필드의 검증(예: 글자 수 부족 등)이 실패했을 때 입력값이 그대로 반환되면,
      평문 비밀번호가 응답 데이터나 브라우저 개발자 도구 네트워크 탭에 고스란히 노출되는 보안 취약점이 발생합니다.
    - 이를 방지하기 위해 `input` 및 `ctx` 필드를 완전히 제거하고, 에러 유형(`type`),
      위치(`loc`), 메시지(`msg`)만을 선별하여 JSON 형식으로 응답합니다.

    Args:
        request (Request): 현재 발생한 HTTP 요청 객체
        exc (RequestValidationError): Pydantic이 발생시킨 유효성 검증 예외 객체

    Returns:
        JSONResponse: 민감 데이터가 제거된 422 상태 코드의 JSON 응답
    """
    # 원본 입력(input, ctx)에 포함될 수 있는 비밀번호를 응답에서 제외한다.
    errors = [
        {"type": error["type"], "loc": error["loc"], "msg": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


# ==============================================================================
# 헬스체크 엔드포인트 (Health Check Endpoint)
# ==============================================================================
@app.get("/health")
def health() -> dict[str, str]:
    """서버의 생존 상태(Liveness/Readiness)를 점검하는 헬스체크 엔드포인트입니다.

    [기술 설명]
    - 로드 밸런서, Docker 컨테이너 헬스체크, 배포 오케스트레이션 도구(Kubernetes 등)에서
      주기적으로 호출하여 인스턴스의 정상 가동 여부를 확인하는 용도로 사용됩니다.

    Returns:
        dict[str, str]: 정상 작동 시 {"status": "ok"} 반환
    """
    return {"status": "ok"}
