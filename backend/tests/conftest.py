"""
AskMate 백엔드 테스트 공통 구성 모듈 (Pytest Test Fixtures Configuration)

[파일 개요]
본 모듈은 pytest 실행 시 전체 테스트 스위트에서 공유하는 공통 픽스처(Fixture)들을 정의합니다.
실제 개발/운영 환경의 `.env` 파일, 데이터베이스, 로그 파일을 오염시키지 않도록
임시 디렉터리(`tmp_path_factory`)를 생성하고 환경 변수를 격리하여 테스트를 수행합니다.

[테스트 격리 및 기술적 설명]
1. 환경 변수 모킹 (MonkeyPatch):
   - `DATABASE_PATH`를 임시 디렉터리 내부의 `test.db`로 유도하여 파일 I/O를 격리합니다.
   - 세션 비밀키(`SESSION_SECRET_KEY`) 및 AI 설정(`AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`)에
     테스트 전용 더미 값을 주입하여 외부 의존성 없이 독립적으로 테스트할 수 있도록 보장합니다.
2. 테스트 간 DB 초기화:
   - 각 테스트 함수 실행 전 `client` 픽스처에서 `Chat` 및 `User` 테이블의 모든 레코드를
     `DELETE`하여 테스트 간 데이터 간섭(Side-effect)을 방지합니다.
3. CSRF 헤더 자동 주입:
   - `client` 픽스처의 기본 헤더로 `X-Requested-With: XMLHttpRequest`를 주입하여
     테스트 코드 작성 시 반복적인 헤더 설정을 줄이고 비즈니스 로직 검증에 집중하도록 지원합니다.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def application(tmp_path_factory):
    """테스트 세션 전체에서 재사용할 격리된 FastAPI 애플리케이션 인스턴스를 생성합니다.

    [기술 설명]
    - 세션 스코프(`scope="session"`)로 단 한 번만 앱을 초기화하여 테스트 수행 시간을 단축합니다.
    - pytest의 `MonkeyPatch` 컨텍스트 매니저를 통해 환경 변수를 테스트용으로 안전하게 오버라이드합니다.
    - `directory`로 작업 디렉터리를 전환(`chdir`)하여 생성되는 `app.log` 등의 파일도 임시 폴더에 격리합니다.

    Yields:
        FastAPI: 초기화된 AskMate 메인 애플리케이션 객체
    """
    directory = tmp_path_factory.mktemp("backend")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_PATH", str(directory / "test.db"))
        patch.setenv("SESSION_SECRET_KEY", "test-session-secret-not-for-deployment")
        patch.setenv("SESSION_MAX_AGE", "3600")
        patch.setenv("SESSION_HTTPS_ONLY", "false")
        # 테스트는 generate_answer를 대체하므로 실제 외부 네트워크 호출은 일어나지 않습니다.
        patch.setenv("AI_API_KEY", "test-ai-key-not-for-deployment")
        patch.setenv("AI_BASE_URL", "https://ai.invalid/v1")
        patch.setenv("AI_MODEL", "test-model")
        patch.setenv("AI_TIMEOUT", "30")
        patch.chdir(directory)

        # 환경 변수가 패치된 상태에서 app 인스턴스를 임포트
        from app.main import app

        yield app


@pytest.fixture
def csrf_headers():
    """POST/PUT/DELETE 등 상태 변경 API 호출 시 요구되는 CSRF 방어용 기본 헤더를 제공합니다.

    Returns:
        dict[str, str]: {"X-Requested-With": "XMLHttpRequest"}
    """
    return {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture
def client(application, csrf_headers):
    """각 테스트 케이스마다 깨끗한 DB 상태를 보장하는 HTTP 테스트 클라이언트를 제공합니다.

    [기술 설명]
    - 함수 스코프 픽스처로서 매 테스트 함수마다 실행됩니다.
    - 테스트 실행 전 `engine.begin()` 트랜잭션 블록 내에서 `Chat`과 `User` 테이블을 삭제하여
      이전 테스트가 남긴 데이터를 완전히 제거합니다.
    - 기본 헤더로 `csrf_headers`가 포함되어 있어 즉시 API 테스트가 가능합니다.

    Yields:
        TestClient: Starlette/FastAPI 테스트 클라이언트 인스턴스
    """
    from app.db_connect import engine
    from app.models.chat import Chat
    from app.models.user import User

    with TestClient(application, headers=csrf_headers) as client:
        # 테스트 간 독립성을 보장하기 위해 DB 테이블 데이터 완전 초기화
        with engine.begin() as connection:
            connection.execute(Chat.__table__.delete())
            connection.execute(User.__table__.delete())
        yield client
