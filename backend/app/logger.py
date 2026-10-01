"""
AskMate 로깅 설정 모듈 (Application Logging Configuration)

파일명   : logger.py
생성자   : Changhwan Kim
생성일   : 2026/09/14
업데이트 : 2026/09/25

[파일 개요]
본 모듈은 애플리케이션 전반에서 사용할 중앙 집중식 로거(`project_logger`)를 설정하고,
콘솔(StreamHandler)과 파일(FileHandler: `app.log`)에 동시에 로그를 기록하도록 파이프라인을 구축합니다.
또한 서드파티 라이브러리(HTTP 클라이언트, OpenAI SDK, Uvicorn 서버)의 로거 수준을 조정하여
로그 가독성을 확보하고 민감정보 유출을 방지합니다.

[주요 기술적 고려사항]
1. 멀티 핸들러 출력:
   - 개발 및 디버깅 편의를 위한 표준 출력(콘솔)과 영구 보관용 UTF-8 인코딩 파일(`app.log`) 동시 출력.
2. 서드파티 HTTP 로거 레벨 조정 (B 담당):
   - `httpx`, `openai`, `httpcore` 등 하위 네트워크 라이브러리가 DEBUG 모드일 때
     발생시키는 과도한 연결 로그(Connection pool, TLS 핸드셰이크 등)를 억제합니다.
   - 요청 1회 단위의 요약만 INFO로 남기고, 저수준 소켓 통신(httpcore)은 WARNING 이상만 기록합니다.
3. 개인정보 및 보안 보호:
   - 사용자의 질문, AI 답변 원문, Authorization 헤더(API 키), 패스워드 해시 등은
     개인정보 보호 및 보안 규정에 따라 로그에 직접 기록하지 않습니다.
4. Uvicorn 로그 단일화:
   - Uvicorn의 기본 핸들러를 제거하고 루트 로거로 전파(`propagate = True`)하여,
     웹 서버 접근 로그와 에러 로그가 `app.log` 파일에도 일관된 형식으로 통합 수집되도록 합니다.
"""

import logging

# ==============================================================================
# 기본 로깅 설정 (Root Logging Configuration)
# ==============================================================================
# DEBUG 레벨 이상의 모든 로그를 콘솔과 파일에 지정된 포맷으로 출력하도록 구성
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),                           # 콘솔(터미널) 표준 출력
        logging.FileHandler("app.log", encoding="utf-8"),  # 로컬 로그 파일 영구 보관
    ],
)

# 애플리케이션 내부에서 공통으로 호출할 전용 로거 인스턴스
logger = logging.getLogger("project_logger")

# ==============================================================================
# 서드파티 라이브러리 로그 레벨 제어 (B 담당)
# ==============================================================================
# AI 통신에 쓰는 HTTP 클라이언트는 루트의 DEBUG 설정에서 연결 단계까지 모두 기록해
# 서비스 로그를 덮는 현상이 발생합니다. 따라서 요청 요약 한 줄(INFO)만 남기고 내부 동작은 경고(WARNING)부터 기록합니다.
# 주의: 질문·답변 내용 및 Authorization 헤더(API 키)는 애플리케이션 로그에 직접 기록하지 않습니다.
# httpx2·httpcore2는 이 프로젝트가 설치한 배포판 이름입니다.
for name in ("httpx", "httpx2", "openai"):
    logging.getLogger(name).setLevel(logging.INFO)

for name in ("httpcore", "httpcore2"):
    logging.getLogger(name).setLevel(logging.WARNING)

# ==============================================================================
# Uvicorn 웹 서버 로거 통합
# ==============================================================================
# Uvicorn 서버 자체 로거(uvicorn, access, error)의 기본 핸들러를 비우고,
# 상위(루트) 로거로 전파되도록 설정하여 콘솔과 app.log 파일 양쪽에 누락 없이 일관되게 기록되도록 만듭니다.
for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uvicorn_logger = logging.getLogger(name)
    uvicorn_logger.handlers.clear()  # 기본 핸들러 제거 (중복 출력 방지)
    uvicorn_logger.propagate = True  # 루트 핸들러(콘솔, app.log)로 전파
