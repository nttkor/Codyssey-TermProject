"""
AskMate 환경 설정 및 기동 검증 테스트 (Configuration & Startup Tests)

[파일 개요]
본 모듈은 별도의 독립 파이썬 서브프로세스(`subprocess.run`)를 실행하여
`config.py` 및 `config_validation.py` 모듈이 다양한 환경 변수 조건(누락, 비정상 포맷,
.env 파일과의 우선순위 관계, HTTPS 쿠키 플래그 등)에서 기대한 대로 엄격하게 검증하고
비정상 기동을 사전에 차단(Fail-Fast)하는지 검증합니다.

[주요 검증 항목]
1. 세션 환경 변수 기동 검증 (`test_invalid_session_settings_fail_startup`):
   - `SESSION_SECRET_KEY` 누락/공백, `SESSION_MAX_AGE`가 숫자가 아니거나 0 이하인 경우,
     `SESSION_HTTPS_ONLY`가 true/false가 아닌 경우 즉각 비정상 종료되는지 확인.
2. AI 연동 환경 변수 기동 검증 (`test_invalid_ai_settings_fail_startup`):
   - `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `AI_TIMEOUT`이 유효하지 않을 때
     외부 API를 호출하는 런타임이 아니라 서버 기동 시점에 프로세스가 종료되는지 확인.
3. 환경 변수 우선순위 검증 (`test_dotenv_and_environment_precedence`):
   - `.env` 파일에 기록된 값보다 셸(Shell) 또는 컨테이너에서 직접 전달한 환경 변수가 우선 적용되는지 확인.
4. HTTPS 전용 쿠키 보안 검증 (`test_https_cookie_is_not_sent_over_http`):
   - `SESSION_HTTPS_ONLY=true` 환경에서 발급된 세션 쿠키가 평문 HTTP 요청에서는 무효화되는지 확인.
5. 배포 사전 검사 스크립트 검증 (`test_deployment_timeout_validation`):
   - CI/CD 파이프라인에서 실행되는 `config_validation.py`의 독립 CLI 동작 검증.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

# 백엔드 루트 경로
BACKEND_DIR = Path(__file__).resolve().parents[1]

# config.py 기동 검증 시 사용할 기본 AI 설정 모의 데이터
# config.py는 AI 설정도 기동 시점에 요구하므로 독립 프로세스 실행을 위해 기본값을 준비합니다.
AI_SETTINGS = {
    "AI_API_KEY": "test-config-ai-key",
    "AI_BASE_URL": "https://ai.invalid/v1",
    "AI_MODEL": "test-model",
    "AI_TIMEOUT": "30",
}
AI_NAMES = (*AI_SETTINGS, )
SESSION_NAMES = ("SESSION_SECRET_KEY", "SESSION_MAX_AGE", "SESSION_HTTPS_ONLY")


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """임시 디렉터리에 독립된 app 패키지와 config 모듈을 복사하여 서브프로세스 테스트 환경을 구성합니다.

    Args:
        tmp_path: pytest가 제공하는 임시 파일 시스템 경로
        monkeypatch: 환경 변수 조작 유틸리티

    Returns:
        Path: 복사된 임시 config.py 파일 경로
    """
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    shutil.copy(BACKEND_DIR / "app/config_validation.py", app_dir / "config_validation.py")
    return Path(shutil.copy(BACKEND_DIR / "app/config.py", app_dir / "config.py"))


@pytest.mark.parametrize(
    "settings, error_name",
    [
        ({}, "SESSION_SECRET_KEY"),
        ({"SESSION_SECRET_KEY": ""}, "SESSION_SECRET_KEY"),
        ({"SESSION_SECRET_KEY": "  "}, "SESSION_SECRET_KEY"),
        ({"SESSION_MAX_AGE": "0"}, "SESSION_MAX_AGE"),
        ({"SESSION_MAX_AGE": "-1"}, "SESSION_MAX_AGE"),
        ({"SESSION_MAX_AGE": "abc"}, "SESSION_MAX_AGE"),
        ({"SESSION_HTTPS_ONLY": "yes"}, "SESSION_HTTPS_ONLY"),
    ],
)
def test_invalid_session_settings_fail_startup(config_file, settings, error_name):
    """세션 관련 환경 변수가 잘못 설정되었을 때 프로세스가 기동을 거부하고 종료되는지 검증합니다."""
    env = os.environ.copy()
    for name in SESSION_NAMES:
        env.pop(name, None)
    env.update(AI_SETTINGS)
    if error_name != "SESSION_SECRET_KEY":
        env["SESSION_SECRET_KEY"] = "test-config-secret"
    env.update(settings)
    result = subprocess.run([sys.executable, str(config_file)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert error_name in result.stderr


@pytest.mark.parametrize(
    "settings, error_name",
    [
        ({}, "AI_API_KEY"),
        ({"AI_API_KEY": "   "}, "AI_API_KEY"),
        ({"AI_BASE_URL": ""}, "AI_BASE_URL"),
        ({"AI_BASE_URL": "ai.invalid/v1"}, "AI_BASE_URL"),
        ({"AI_MODEL": ""}, "AI_MODEL"),
        ({"AI_TIMEOUT": "0"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "-1"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "abc"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "nan"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "inf"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "-inf"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "1e999"}, "AI_TIMEOUT"),
        ({"AI_TIMEOUT": "0.0"}, "AI_TIMEOUT"),
    ],
)
def test_invalid_ai_settings_fail_startup(config_file, settings, error_name):
    """AI 연동 관련 설정 오류 시 첫 질문 시점이 아니라 서버 기동 시점에 즉시 실패하는지 검증합니다."""
    env = os.environ.copy()
    for name in (*SESSION_NAMES, *AI_NAMES):
        env.pop(name, None)
    env["SESSION_SECRET_KEY"] = "test-config-secret"
    env.update({name: value for name, value in AI_SETTINGS.items() if name != error_name})
    env.update(settings)
    result = subprocess.run([sys.executable, str(config_file)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert error_name in result.stderr


def test_ai_settings_are_read_from_environment(config_file):
    """환경 변수에 지정된 유효한 AI 설정값들이 config 모듈에 정확하게 로드되는지 검증합니다."""
    env = os.environ.copy()
    for name in (*SESSION_NAMES, *AI_NAMES):
        env.pop(name, None)
    env["SESSION_SECRET_KEY"] = "test-config-secret"
    env.update(AI_SETTINGS)
    env["AI_TIMEOUT"] = "12.5"
    script = """
import runpy, sys
config = runpy.run_path(sys.argv[1])
assert config['AI_API_KEY'] == 'test-config-ai-key'
assert config['AI_BASE_URL'] == 'https://ai.invalid/v1'
assert config['AI_MODEL'] == 'test-model'
assert config['AI_TIMEOUT'] == 12.5
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(config_file)], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_dotenv_and_environment_precedence(config_file, tmp_path):
    """실행 셸 환경 변수가 .env 파일에 작성된 값보다 높은 우선순위를 갖는지 검증합니다."""
    (tmp_path / ".env").write_text(
        "SESSION_SECRET_KEY=dotenv-test-key\nSESSION_MAX_AGE=1800\n"
        "SESSION_HTTPS_ONLY=true\nDATABASE_PATH=state/test.db\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    for name in (*SESSION_NAMES, "DATABASE_PATH"):
        env.pop(name, None)
    env.update(AI_SETTINGS)
    script = """
import runpy, sys
config = runpy.run_path(sys.argv[1])
assert config['SESSION_SECRET_KEY'] == sys.argv[2]
assert config['SESSION_MAX_AGE'] == int(sys.argv[3])
assert config['SESSION_HTTPS_ONLY'] is True
assert config['DATABASE_PATH'] == config['BACKEND_DIR'] / 'state/test.db'
"""
    for settings, expected_key, expected_age in [
        ({}, "dotenv-test-key", "1800"),
        ({"SESSION_SECRET_KEY": "shell-test-key", "SESSION_MAX_AGE": "600"}, "shell-test-key", "600"),
    ]:
        result = subprocess.run(
            [sys.executable, "-c", script, str(config_file), expected_key, expected_age],
            env={**env, **settings}, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr


def test_https_cookie_is_not_sent_over_http(tmp_path):
    """SESSION_HTTPS_ONLY=true 설정 시 쿠키에 Secure 플래그가 붙고 평문 HTTP에서 거부되는지 검증합니다."""
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "DATABASE_PATH": str(tmp_path / "https.db"),
        "SESSION_SECRET_KEY": "https-cookie-test-secret",
        "SESSION_MAX_AGE": "120",
        "SESSION_HTTPS_ONLY": "true",
        **AI_SETTINGS,
    }
    script = """
from fastapi.testclient import TestClient
from app.main import app
credentials = {'username': 'https_user', 'password': 'a long test password'}
with TestClient(app, base_url='https://testserver', headers={'X-Requested-With': 'XMLHttpRequest'}) as client:
    assert client.post('/api/signup', json=credentials).status_code == 201
    response = client.post('/api/login', json=credentials)
    assert response.status_code == 200
    assert 'secure' in response.headers['set-cookie'].lower()
    assert 'Max-Age=120' in response.headers['set-cookie']
    assert client.get('/api/me').status_code == 200
    assert client.get('http://testserver/api/me').status_code == 401
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value, valid", [
    ("nan", False), ("inf", False), ("-inf", False), ("1e999", False),
    ("0", False), ("0.0", False), ("-1", False), ("abc", False),
    ("0.5", True), ("30", True), ("1e1", True),
])
def test_deployment_timeout_validation(value, valid):
    """배포 워크플로(GitHub Actions)에서 사용하는 표준 라이브러리 검증 스크립트의 동작을 검증합니다."""
    result = subprocess.run(
        [sys.executable, str(BACKEND_DIR / "app/config_validation.py")],
        env={**os.environ, "AI_TIMEOUT": value}, capture_output=True, text=True,
    )
    assert (result.returncode == 0) == valid
    if not valid:
        assert "AI_TIMEOUT" in result.stderr
