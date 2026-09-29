"""실행 위치와 관계없이 공통 경로와 환경변수를 읽는다."""

import os
from pathlib import Path

from dotenv import load_dotenv

from app.config_validation import parse_ai_timeout

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent

# 배포 환경에서 전달한 값이 로컬 .env보다 우선한다.
load_dotenv(BACKEND_DIR / ".env", override=False)

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/askmate.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BACKEND_DIR / DATABASE_PATH

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "").strip()
if not SESSION_SECRET_KEY:
    raise RuntimeError("SESSION_SECRET_KEY를 .env 또는 실행 환경에 설정하세요.")

try:
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "3600"))
except ValueError:
    raise RuntimeError("SESSION_MAX_AGE는 초 단위의 양의 정수여야 합니다.") from None
if SESSION_MAX_AGE <= 0:
    raise RuntimeError("SESSION_MAX_AGE는 초 단위의 양의 정수여야 합니다.")

_https_only = os.getenv("SESSION_HTTPS_ONLY", "false").strip().lower()
if _https_only not in ("true", "false"):
    raise RuntimeError("SESSION_HTTPS_ONLY는 true 또는 false여야 합니다.")
SESSION_HTTPS_ONLY = _https_only == "true"

# B 담당: AI 통신 설정.
# 외부 게이트웨이를 처음 호출할 때가 아니라 애플리케이션 기동 시점에 설정 오류를
# 발견하도록 필수 값과 형식을 여기서 검증한다. 배포 환경변수가 로컬 .env보다 우선한다.
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY를 .env 또는 실행 환경에 설정하세요.")

AI_BASE_URL = os.getenv("AI_BASE_URL", "").strip()
if not AI_BASE_URL:
    raise RuntimeError("AI_BASE_URL을 .env 또는 실행 환경에 설정하세요.")
if not AI_BASE_URL.startswith(("http://", "https://")):
    raise RuntimeError("AI_BASE_URL은 http:// 또는 https://로 시작해야 합니다.")

AI_MODEL = os.getenv("AI_MODEL", "").strip()
if not AI_MODEL:
    raise RuntimeError("AI_MODEL을 .env 또는 실행 환경에 설정하세요.")

# OpenAI SDK의 요청 타임아웃(초). 배포 사전 검사와 같은 검증을 사용한다.
AI_TIMEOUT = parse_ai_timeout(os.getenv("AI_TIMEOUT", "30"))
