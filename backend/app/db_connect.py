"""
AskMate 데이터베이스 연결 및 세션 관리 모듈 (Database Connection & Session Management)

파일명   : db_connect.py
생성자   : Changhwan Kim
생성일   : 2026/09/14
업데이트 : 2026/09/20

[파일 개요]
본 모듈은 SQLite 데이터베이스와의 연결을 수립하고, SQLAlchemy 2.0 ORM 기반의
공통 모델 베이스 클래스(`Base`) 및 요청 단위 트랜잭션 관리를 위한 세션 팩토리(`SessionLocal`)를 제공합니다.
애플리케이션 기동 시점의 DB 초기화 및 연결 상태 점검 기능을 포함합니다.

[주요 기술 설명]
1. SQLite 엔진 설정:
   - `check_same_thread=False`: FastAPI는 비동기 이벤트 루프와 스레드 풀(Threadpool)을 오가며
     요청을 처리하므로, 동일 스레드 제약을 해제해야 멀티스레드 환경에서 안전하게 세션을 공유할 수 있습니다.
   - `hide_parameters=True`: SQL 쿼리 실패 시 로그나 예외 객체에 비밀번호 해시, 개인 대화 내용 등의
     바인딩 파라미터가 노출되지 않도록 마스킹하여 보안을 강화합니다.
2. 외래키(Foreign Key) 활성화:
   - SQLite는 성능 및 하위 호환성을 이유로 기본적으로 외래키 제약조건 검사를 비활성화해 둡니다.
     새 커넥션이 생성될 때마다 `PRAGMA foreign_keys=ON`을 실행하여 참조 무결성을 강제합니다.
3. 세션 라이프사이클 관리:
   - FastAPI의 의존성 주입(Dependency Injection) 시스템과 연동되는 `get_db()` 제너레이터를 통해
     각 HTTP 요청마다 독립된 세션을 열고, 요청 종료 시 자동으로 안전하게 세션을 반환/닫습니다.
"""

from collections.abc import Generator

from sqlalchemy import URL, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_PATH
from app.logger import logger

# ==============================================================================
# SQLAlchemy 엔진 및 세션 팩토리 생성
# ==============================================================================
# SQLite 연결 엔진 생성
engine = create_engine(
    URL.create("sqlite", database=str(DATABASE_PATH)),
    connect_args={"check_same_thread": False},  # FastAPI 비동기/멀티스레드 환경 지원
    hide_parameters=True,  # DB 예외 로그에 비밀번호 해시 등 SQL 인자 노출 방지 (보안 조치)
)

# 스레드 세이프한 세션 팩토리
SessionLocal = sessionmaker(bind=engine)


# ==============================================================================
# ORM 모델 베이스 클래스 (Declarative Base)
# ==============================================================================
class Base(DeclarativeBase):
    """모든 SQLAlchemy ORM 모델 클래스가 상속받아야 하는 공통 선언적 베이스 클래스.

    [기술 설명]
    SQLAlchemy 2.0 스타일의 타입 어노테이션 기반 `Mapped`, `mapped_column` 선언을
    지원하며, 모든 파생 모델의 테이블 메타데이터를 `Base.metadata`에 통합 수집합니다.
    """


# ==============================================================================
# SQLite 커넥션 이벤트 리스너
# ==============================================================================
@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, connection_record):
    """새로운 SQLite DB 커넥션이 열릴 때마다 외래키 제약조건 검사를 활성화합니다.

    [기술 설명]
    SQLite 엔진은 연결별로 외래키 활성화 상태가 유지되므로, 커넥션 풀에서 새 연결이
    초기화될 때마다 PRAGMA foreign_keys=ON 명령을 명시적으로 실행해야
    chats.user_id 등의 외래키 참조 무결성이 보장됩니다.

    Args:
        connection: 새로 생성된 하위 DBAPI(sqlite3) 연결 객체
        connection_record: SQLAlchemy 커넥션 풀 레코드 정보
    """
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ==============================================================================
# DB 연결 점검 및 초기화 함수
# ==============================================================================
def check_connection() -> None:
    """데이터베이스 디렉터리 존재 여부를 확인하고 연결 유효성을 점검합니다.

    [기술 설명]
    1. 데이터베이스 파일이 위치할 상위 디렉터리(예: data/)가 없으면 자동으로 생성합니다.
    2. 엔진으로부터 연결을 획득하여 간단한 쿼리(`SELECT 1`)를 수행함으로써
       파일 읽기/쓰기 권한 및 SQLite 동작 상태를 검증합니다.
    3. 실패 시 예외를 로깅하고 상위로 전파하여 서버 기동을 즉각 중단(Fail-Fast)합니다.

    Raises:
        Exception: 디렉터리 생성 실패 또는 SQLite 연결 실패 시 발생
    """
    try:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("db_connection_success")
    except Exception:
        logger.exception("db_connection_failure")
        raise


def get_db() -> Generator[Session, None, None]:
    """FastAPI 경로 작동 함수(Route handler)에 주입할 요청별 독립 DB 세션을 제공합니다.

    [기술 설명]
    - FastAPI의 `Depends(get_db)`를 통해 호출되며 Python 제너레이터(컨텍스트 매니저)로 동작합니다.
    - 요청 시작 시 `SessionLocal()`로 세션을 생성하고 `yield`로 전달합니다.
    - 요청 처리가 끝나면(성공 또는 에러 무관) `finally` 블록에서 세션을 자동으로 닫습니다.
    - 트랜잭션 원자성을 위해 쓰기 작업의 commit 및 rollback은 세션을 사용하는 비즈니스 로직에서 명시적으로 제어합니다.

    Yields:
        Session: 현재 요청의 전용 SQLAlchemy 세션 인스턴스
    """
    with SessionLocal() as session:
        yield session


def init_db() -> None:
    """데이터베이스 연결을 확인하고 정의된 테이블 스키마를 초기화합니다.

    [기술 설명]
    1. `app.models` 하위의 `chat`, `user` 모듈을 임포트하여 ORM 모델이 `Base.metadata`에
       정상적으로 등록되도록 유도합니다.
    2. `check_connection()`으로 디렉터리와 기본 연결을 점검합니다.
    3. `Base.metadata.create_all()`을 실행하여 아직 DB에 존재하지 않는 테이블(users, chats)을 자동 생성합니다.
       (이미 존재하는 테이블은 덮어쓰지 않고 보존됩니다.)
    """
    from app.models import chat, user  # 테이블 정의를 Base.metadata에 등록하기 위한 지연 임포트

    check_connection()
    Base.metadata.create_all(bind=engine)
