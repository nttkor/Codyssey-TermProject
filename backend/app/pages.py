"""
AskMate 프론트엔드 HTML 페이지 라우터 (Frontend Page Rendering & Access Guard Router)

[파일 개요]
본 모듈은 Jinja2 템플릿 엔진을 사용하여 사용자가 웹 브라우저에서 직접 접근하는
HTML 웹 페이지 뷰(View)를 렌더링하고, 로그인 세션 유무에 따라 적절한 화면으로
리다이렉션하는 서버 사이드 페이지 접근 제어(Page Access Guard)를 담당합니다.

[보안 및 기술적 고려사항]
1. 접근 권한에 따른 조건부 리다이렉트 (HTTP 303 See Other):
   - 비인가 보호: 비로그인 사용자가 대화창(`/chat`) 또는 대화 기록(`/history`)에 접근하면
     즉시 로그인 페이지(`/login`)로 강제 리다이렉트합니다.
   - 불필요한 재로그인 방지: 이미 로그인된 사용자가 로그인(`/login`) 또는 회원가입(`/signup`) 페이지에
     접근하면 바로 서비스 메인 화면인 대화창(`/chat`)으로 안내합니다.
2. HTTP 303 vs 307 상태 코드:
   - 루트(`/`)의 경우 단순 안내 성격으로 임시 이동(307 Temporary Redirect)을 사용하며,
     인증 상태에 따른 화면 전환에는 표준에 따라 GET 메서드로의 전환을 보장하는 303 See Other를 사용합니다.
3. 민감한 렌더링 결과의 브라우저 캐싱 방지:
   - 사용자 개인정보나 대화 인터페이스가 포함된 `/chat` 및 `/history` 화면 응답 헤더에
     `Cache-Control: no-store`를 명시하여 뒤로 가기 등으로 인한 정보 유출을 예방합니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import get_session_user
from app.config import APP_DIR
from app.models.user import User

# 페이지 렌더링 라우터 인스턴스
router = APIRouter()

# Jinja2 템플릿 디렉터리 바인딩
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


@router.get("/", include_in_schema=False)
def index():
    """루트 경로('/') 접근 시 로그인 페이지('/login')로 리다이렉트합니다.

    [기술 설명]
    - OpenAPI/Swagger 스키마 문서에는 표시되지 않도록 `include_in_schema=False`를 지정합니다.
    - 브라우저 최초 유입 시 기본 시작 화면인 로그인 페이지로 HTTP 307 임시 리다이렉션을 수행합니다.

    Returns:
        RedirectResponse: /login 경로로의 307 리다이렉트 응답
    """
    return RedirectResponse(url="/login", status_code=307)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: Annotated[User | None, Depends(get_session_user)]):
    """로그인 HTML 화면을 렌더링하거나, 이미 로그인된 경우 대화 화면으로 이동시킵니다.

    [기술 설명]
    - 세션에 유효한 사용자가 이미 존재하면 추가 로그인 과정이 불필요하므로 `/chat`으로 303 리다이렉트합니다.
    - 비로그인 상태인 경우 `login.html` 템플릿을 브라우저에 반환합니다.

    Args:
        request (Request): 템플릿 렌더링에 필요한 HTTP 요청 객체
        user (User | None): 현재 세션의 사용자 객체 (비로그인 시 None)

    Returns:
        HTMLResponse | RedirectResponse: 로그인 HTML 뷰 또는 대화창 리다이렉트
    """
    if user is not None:
        return RedirectResponse(url="/chat", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, user: Annotated[User | None, Depends(get_session_user)]):
    """회원가입 HTML 화면을 렌더링하거나, 이미 로그인된 경우 대화 화면으로 이동시킵니다.

    [기술 설명]
    - 이미 인증된 세션을 가진 사용자가 접근하면 `/chat`으로 리다이렉트합니다.
    - 미인증 사용자에게는 계정 생성을 위한 `signup.html` 템플릿을 반환합니다.

    Args:
        request (Request): HTTP 요청 객체
        user (User | None): 현재 세션의 사용자 객체

    Returns:
        HTMLResponse | RedirectResponse: 회원가입 HTML 뷰 또는 대화창 리다이렉트
    """
    if user is not None:
        return RedirectResponse(url="/chat", status_code=303)
    return templates.TemplateResponse(request=request, name="signup.html")


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, user: Annotated[User | None, Depends(get_session_user)]):
    """AI 대화창 HTML 화면을 렌더링합니다. 로그인이 필요한 보호된 페이지입니다.

    [기술 설명]
    1. 비로그인 상태(`user is None`)인 경우 접근을 제한하고 `/login`으로 303 리다이렉트합니다.
    2. 로그인 상태인 경우 사용자 정보(`user`)를 템플릿 컨텍스트에 전달하여 네비게이션 바 등에
       사용자명이 표시될 수 있도록 렌더링합니다.
    3. `Cache-Control: no-store` 헤더를 설정하여 비인가 단말 캐싱을 방지합니다.

    Args:
        request (Request): HTTP 요청 객체
        user (User | None): 현재 세션의 사용자 객체

    Returns:
        HTMLResponse | RedirectResponse: 채팅 인터페이스 HTML 또는 로그인 페이지 리다이렉트
    """
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="chat.html", context={"user": user}, headers={"Cache-Control": "no-store"}
    )


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, user: Annotated[User | None, Depends(get_session_user)]):
    """사용자의 대화 기록 열람 HTML 화면을 렌더링합니다. 로그인이 필요한 보호된 페이지입니다.

    [기술 설명]
    1. 미인증 접근 시 `/login`으로 303 리다이렉트합니다.
    2. 인증된 사용자에게 대화 기록을 렌더링할 컨테이너가 포함된 `history.html` 템플릿을 반환합니다.
       (실제 대화 데이터는 브라우저가 로드된 후 `/api/me/chats` 비동기 호출을 통해 동적으로 채워집니다.)
    3. 개인 이력 보호를 위해 응답 헤더에 `Cache-Control: no-store`를 적용합니다.

    Args:
        request (Request): HTTP 요청 객체
        user (User | None): 현재 세션의 사용자 객체

    Returns:
        HTMLResponse | RedirectResponse: 히스토리 HTML 뷰 또는 로그인 페이지 리다이렉트
    """
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="history.html", context={"user": user}, headers={"Cache-Control": "no-store"}
    )
