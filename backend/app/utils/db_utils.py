"""
AskMate 데이터베이스 점검 및 통계 유틸리티 모듈 (Database Utilities)

[파일 개요]
본 모듈은 데이터베이스 상태 확인, 테이블 레코드 수 집계, 스키마 인스펙션 등
운영 및 디버깅 시 자주 필요한 DB 분석 기능을 모듈화하여 제공합니다.
일회성 쿼리 스크립트를 매번 작성할 필요 없이 본 모듈의 함수를 재사용할 수 있습니다.
"""

from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.db_connect import SessionLocal, engine
from app.models.chat import Chat
from app.models.user import User


def get_table_counts(db: Session | None = None) -> dict[str, int]:
    """주요 테이블(users, chats)의 전체 레코드 수를 조회하여 반환합니다.

    Args:
        db (Session | None): 기존 세션 객체. None이면 새 세션을 열어 조회 후 닫음.

    Returns:
        dict[str, int]: {"users": int, "chats": int} 형식의 레코드 수 딕셔너리
    """
    def _count(session: Session) -> dict[str, int]:
        user_count = session.scalar(select(func.count()).select_from(User)) or 0
        chat_count = session.scalar(select(func.count()).select_from(Chat)) or 0
        return {"users": user_count, "chats": chat_count}

    if db is not None:
        return _count(db)
    with SessionLocal() as session:
        return _count(session)


def inspect_db_schema() -> dict[str, list[str]]:
    """데이터베이스 엔진을 검사하여 존재하는 테이블 목록과 각 테이블의 컬럼 이름들을 반환합니다.

    Returns:
        dict[str, list[str]]: 테이블명을 키로 하고 컬럼 이름 리스트를 값으로 갖는 딕셔너리
    """
    inspector = inspect(engine)
    result = {}
    for table_name in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        result[table_name] = columns
    return result


def get_user_summary(user_id: int, db: Session | None = None) -> dict[str, Any] | None:
    """특정 사용자의 기본 정보와 누적 대화 기록 수를 조회하여 반환합니다.

    Args:
        user_id (int): 조회할 사용자 ID
        db (Session | None): 세션 객체 (선택)

    Returns:
        dict[str, Any] | None: 사용자 요약 정보 또는 미존재 시 None
    """
    def _summary(session: Session) -> dict[str, Any] | None:
        user = session.get(User, user_id)
        if user is None:
            return None
        chat_count = session.scalar(
            select(func.count()).select_from(Chat).where(Chat.user_id == user_id)
        ) or 0
        return {
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at,
            "chat_count": chat_count,
        }

    if db is not None:
        return _summary(db)
    with SessionLocal() as session:
        return _summary(session)


if __name__ == "__main__":
    # CLI 단독 실행 시 현재 데이터베이스 상태를 요약 출력
    counts = get_table_counts()
    print("=== AskMate DB Status ===")
    print(f"Users: {counts['users']}")
    print(f"Chats: {counts['chats']}")
    print("Schema:", inspect_db_schema())
