"""
AskMate 전역 설정 및 환경 변수 관리 모듈 (Application Configuration)

[파일 개요]
본 모듈은 실행 위치(Working Directory)와 무관하게 프로젝트 기준의 절대 경로를 확정하고,
`.env` 파일 및 운영체제 환경 변수로부터 시스템 전역 설정을 로드·검증합니다.
서버 기동 시점(Fail-Fast)에 필수 설정의 누락이나 잘못된 형식을 즉시 탐지하여
런타임에 발생할 수 있는 잠재적 장애를 미연에 방지합니다.

[설계 원칙 및 기술 설명]
1. 경로 일관성:
   - `__file__` 기반으로 `APP_DIR`과 `BACKEND_DIR`을 결정하므로, 어느 작업 디렉터리에서
     명령어를 실행하더라도 정적 파일, 템플릿, SQLite DB 파일 경로가 항상 정확하게 참조됩니다.
2. 환경 변수 우선순위:
   - `dotenv.load_dotenv(..., override=False)`를 사용하여 컨테이너 배포 환경(Docker, K8s 등)이나
     셸(Shell)에서 직접 주입한 환경 변수가 로컬 `.env` 파일의 내용보다 우선하도록 보장합니다.
3. 기동 시 검증 (Fail-Fast Validation):
   - 보안 필수값(`SESSION_SECRET_KEY`), 세션 만료 시간(`SESSION_MAX_AGE`),
     AI 통신 정보(`AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `AI_TIMEOUT`)가
     올바르게 설정되지 않으면 서버 기동을 즉시 중단하고 명확한 예외 메시지를 발생시킵니다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from app.config_validation import parse_ai_timeout

# ==============================================================================
# 경로 설정 (Path Configurations)
# ==============================================================================
# 현재 파일(config.py)이 위치한 디렉터리 (/backend/app)
APP_DIR = Path(__file__).resolve().parent

# 백엔드 프로젝트 루트 디렉터리 (/backend)
BACKEND_DIR = APP_DIR.parent

# ==============================================================================
# 환경 변수 로드 (.env Loader)
# ==============================================================================
# override=False: 시스템 환경 변수나 Docker 환경 변수가 .env 파일의 값보다 우선순위를 갖습니다.
load_dotenv(BACKEND_DIR / ".env", override=False)

# ==============================================================================
# 데이터베이스 설정 (Database Configurations)
# ==============================================================================
# DATABASE_PATH가 상대 경로로 지정된 경우 BACKEND_DIR 기준으로 절대 경로화합니다.
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/askmate.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BACKEND_DIR / DATABASE_PATH

# ==============================================================================
# 세션 및 보안 설정 (Session & Security Configurations)
# ==============================================================================
# 세션 서명 및 암호화에 사용되는 비밀 키 (필수값)
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "").strip()
if not SESSION_SECRET_KEY:
    raise RuntimeError("SESSION_SECRET_KEY를 .env 또는 실행 환경에 설정하세요.")

# 세션 유지 유효 시간 (초 단위 양의 정수, 기본값 3600초 = 1시간)
try:
    SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "3600"))
except ValueError:
    raise RuntimeError("SESSION_MAX_AGE는 초 단위의 양의 정수여야 합니다.") from None
if SESSION_MAX_AGE <= 0:
    raise RuntimeError("SESSION_MAX_AGE는 초 단위의 양의 정수여야 합니다.")

# HTTPS 전송 전용 쿠키 플래그 (Secure 플래그)
# 개발 환경에서는 "false", 운영(배포) 환경에서는 "true"로 설정하여 평문 HTTP를 통한 쿠키 탈취를 방지합니다.
_https_only = os.getenv("SESSION_HTTPS_ONLY", "false").strip().lower()
if _https_only not in ("true", "false"):
    raise RuntimeError("SESSION_HTTPS_ONLY는 true 또는 false여야 합니다.")
SESSION_HTTPS_ONLY = _https_only == "true"

# ==============================================================================
# AI 연동 설정 (AI Service Configurations - B 담당)
# ==============================================================================
# 외부 게이트웨이를 처음 호출할 때가 아니라 애플리케이션 기동 시점에 설정 오류를
# 발견하도록 필수 값과 형식을 여기서 검증합니다. 배포 환경변수가 로컬 .env보다 우선합니다.

# AI API 인증 키 (필수값)
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY를 .env 또는 실행 환경에 설정하세요.")

# OpenAI 호환 API 게이트웨이 엔드포인트 URL (필수값, http:// 또는 https:// 스키마 필수)
AI_BASE_URL = os.getenv("AI_BASE_URL", "").strip()
if not AI_BASE_URL:
    raise RuntimeError("AI_BASE_URL을 .env 또는 실행 환경에 설정하세요.")
if not AI_BASE_URL.startswith(("http://", "https://")):
    raise RuntimeError("AI_BASE_URL은 http:// 또는 https://로 시작해야 합니다.")

# 호출 대상 AI 모델 식별자 (필수값)
AI_MODEL = os.getenv("AI_MODEL", "").strip()
if not AI_MODEL:
    raise RuntimeError("AI_MODEL을 .env 또는 실행 환경에 설정하세요.")

# OpenAI SDK 요청 타임아웃 (초 단위 유한한 양수, 기본값 30초)
# 배포 사전 검증(app.config_validation)과 동일한 파싱/검증 로직을 공유합니다.
AI_TIMEOUT = parse_ai_timeout(os.getenv("AI_TIMEOUT", "30"))
