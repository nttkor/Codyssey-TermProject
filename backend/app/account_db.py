"""
AskMate 사용자 계정 데이터 액세스 모듈 (Account Database Access Layer)

[파일 개요]
본 모듈은 `users` 테이블에 대한 영속성(CRUD) 작업을 수행하는 데이터 액세스 계층(DAL)입니다.
FastAPI 라우터 및 비즈니스 계층으로부터 DB 세션과 매개변수를 전달받아 안전하게 쿼리를 수행하며,
데이터베이스 처리 중 발생하는 예외는 트랜잭션 롤백 후 상위 계층으로 전달하여
라우터가 적절한 HTTP 상태 코드(예: 409 Conflict, 500 Internal Server Error)로 변환할 수 있도록 설계되었습니다.

[주요 기술 설명]
1. 원자적 트랜잭션 및 자동 롤백:
   - 신규 사용자 추가 시 `db.flush()`를 통해 기본키 ID를 즉시 생성 및 획득한 후 `commit()`합니다.
   - 예외 발생 시 세션 상태가 오염되지 않도록 즉시 `rollback()`을 수행합니다.
2. SQLAlchemy 2.0 스타일 쿼리:
   - 레거시 Query API 대신 `select()` 구문과 `db.scalar()`, `db.get()` 메서드를 사용하여
     타입 안정성과 최적화된 실행 계획을 보장합니다.
"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User


def create_user(db: Session, username: str, password_hash: str) -> int:
    """신규 사용자를 데이터베이스에 저장하고 발급된 고유 사용자 ID를 반환합니다.

    [기술 설명]
    1. 전달받은 정규화된 username과 암호화된 password_hash로 User 엔티티를 생성하여 세션에 추가합니다.
    2. `db.flush()`를 실행하여 DB 엔진에 INSERT 문을 전송하고, 데이터베이스가 자동 채번한 `user.id`를 추출합니다.
    3. `db.commit()`을 통해 트랜잭션을 영구 반영합니다.
    4. 중복 사용자명(UNIQUE 제약 위반)이나 DB 장애 발생 시 즉시 `db.rollback()`을 호출하여
       세션을 안전한 상태로 복원하고 발생한 `SQLAlchemyError`를 상위로 재전파합니다.

    Args:
        db (Session): 요청 라이프사이클에 바인딩된 SQLAlchemy DB 세션
        username (str): 정규화(소문자화, 공백 제거)된 사용자명
        password_hash (str): Argon2id로 해싱된 비밀번호 문자열

    Returns:
        int: 새로 생성된 사용자의 고유 ID (Primary Key)

    Raises:
        SQLAlchemyError: 중복 사용자명(IntegrityError)이나 데이터베이스 입출력 실패 시 발생
    """
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    try:
        db.flush()
        user_id = user.id
        db.commit()
    except SQLAlchemyError:
        # 트랜잭션 롤백을 수행하여 세션 내 보류 중인 변경사항을 취소하고 연결을 정상 상태로 유지
        db.rollback()
        raise
    return user_id


def get_user_by_username(db: Session, username: str) -> User | None:
    """사용자명(username)을 조건으로 일치하는 사용자 엔티티를 조회합니다.

    [기술 설명]
    - 로그인 인증 처리 시 클라이언트가 제공한 사용자명을 바탕으로 계정을 검색할 때 사용됩니다.
    - `username` 컬럼에 UNIQUE 인덱스가 적용되어 있으므로 최대 1개의 레코드만 반환됩니다.

    Args:
        db (Session): SQLAlchemy DB 세션
        username (str): 조회할 정규화된 사용자명

    Returns:
        User | None: 일치하는 사용자가 존재하면 User 객체, 없으면 None 반환
    """
    return db.scalar(select(User).where(User.username == username))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """기본 키(Primary Key)인 user_id를 기반으로 사용자 엔티티를 조회합니다.

    [기술 설명]
    - 세션 쿠키에 저장된 user_id를 바탕으로 현재 로그인된 사용자의 실존 여부 및 계정 정보를
      확인하는 세션 종속성 검사(`get_session_user`)에서 호출됩니다.
    - SQLAlchemy의 `db.get()`은 1차 캐시(Identity Map)를 우선 탐색하므로 불필요한 SQL 실행을 줄입니다.

    Args:
        db (Session): SQLAlchemy DB 세션
        user_id (int): 조회할 사용자의 고유 식별자(PK)

    Returns:
        User | None: 일치하는 사용자가 존재하면 User 객체, 없으면 None 반환
    """
    return db.get(User, user_id)
