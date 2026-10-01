"""
AskMate 대화 기록 데이터 액세스 모듈 (Chat Database Access Layer)

[파일 개요]
본 모듈은 `chats` 테이블에 대한 데이터베이스 CRUD 작업을 전담하는 데이터 액세스 계층(DAL)입니다.
사용자의 질문과 AI의 응답을 트랜잭션 단위로 안전하게 저장하고, 대화 이력 화면 렌더링용
전체 기록 조회 및 다중 턴(Multi-turn) 대화 문맥 주입을 위한 최근 5쌍의 대화 추출 기능을 제공합니다.

[주요 기술 설명]
1. 안정적인 정렬 기준 (Stable Sorting):
   - SQLite 시간 정밀도나 동일 시각 생성 레코드 발생 시 순서 왜곡을 방지하기 위해
     항상 `created_at DESC, id DESC`의 복합 정렬 기준을 사용합니다.
2. AI 문맥용 슬라이싱 및 시간순 복원:
   - AI 호출 시 직전 대화 흐름을 파악하기 위해 최신 대화 5쌍을 우선 내림차순(최신순)으로 5개만 추출한 뒤,
     `chats.reverse()`를 통해 대화가 일어난 순서인 오름차순(과거 -> 최신)으로 복원하여 LLM에 전달합니다.
3. 원자적 저장 및 롤백:
   - AI 답변 수신이 완료된 이후에만 `create_chat`을 호출하며, DB 저장 실패 시 세션을 즉시 롤백합니다.
"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.chat import Chat


def create_chat(db: Session, user_id: int, question: str, answer: str) -> int:
    """질문과 AI 답변 한 쌍을 데이터베이스에 영구 저장하고 생성된 기록 ID를 반환합니다.

    [기술 설명]
    1. Chat 엔티티를 생성하고 세션에 등록한 뒤 `db.flush()`로 INSERT를 실행합니다.
    2. 생성된 레코드의 기본 키 `chat.id`를 확보한 후 `db.commit()`으로 영구 저장합니다.
    3. 저장 도중 외래키 제약조건 위반이나 디스크 장애 등 `SQLAlchemyError`가 발생하면
       `db.rollback()`을 호출하여 세션을 정리한 후 예외를 상위로 재전파합니다.

    Args:
        db (Session): SQLAlchemy 세션 객체
        user_id (int): 질문을 등록한 회원의 고유 ID (users.id 참조)
        question (str): 사용자의 질문 본문 텍스트
        answer (str): AI가 생성한 응답 답변 본문 텍스트

    Returns:
        int: 새로 생성된 대화 레코드의 고유 식별자 ID (Primary Key)

    Raises:
        SQLAlchemyError: DB 쓰기 작업 실패 시 발생
    """
    chat = Chat(user_id=user_id, question=question, answer=answer)
    db.add(chat)
    try:
        db.flush()
        chat_id = chat.id
        db.commit()
    except SQLAlchemyError:
        # 트랜잭션 오류 발생 시 보류 중인 변경사항을 즉시 롤백하여 세션을 깨끗한 상태로 유지
        db.rollback()
        raise
    return chat_id


def get_chats_by_user(db: Session, user_id: int) -> list[Chat]:
    """특정 사용자의 전체 대화 기록을 생성 시각 및 ID 내림차순(최신순)으로 조회합니다.

    [기술 설명]
    - 대화 내역 조회 API(`/api/me/chats`)에서 호출됩니다.
    - `user_id` 인덱스를 활용하여 특정 사용자의 대화만 빠르게 필터링합니다.
    - 정렬 순서는 `created_at.desc(), id.desc()`로, 동일한 시각에 생성된 레코드라도
      고유 ID를 통해 정렬 결과가 항상 일관되게 유지되도록 보장합니다.

    Args:
        db (Session): SQLAlchemy 세션 객체
        user_id (int): 대화 기록을 조회할 대상 사용자 ID

    Returns:
        list[Chat]: 최신순으로 정렬된 대화 엔티티 객체 목록 (기록이 없으면 빈 리스트)
    """
    statement = (
        select(Chat)
        .where(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc(), Chat.id.desc())
    )
    return list(db.scalars(statement))


def get_recent_chats_by_user(db: Session, user_id: int) -> list[Chat]:
    """AI 프롬프트 문맥 주입용으로 특정 사용자의 최근 대화 최대 5쌍을 과거 순서대로 반환합니다.

    [기술 설명]
    1. SQL 수준에서 `ORDER BY created_at DESC, id DESC LIMIT 5`를 실행하여
       해당 사용자의 가장 최신 대화 5개를 신속하게 가져옵니다.
    2. 데이터베이스에서 가져온 결과는 최신순(내림차순)이므로,
       LLM이 대화 흐름을 시간순으로 자연스럽게 이해할 수 있도록
       파이썬 리스트의 `reverse()` 메서드를 호출하여 오래된 순(오름차순)으로 뒤집어 반환합니다.

    Args:
        db (Session): SQLAlchemy 세션 객체
        user_id (int): 현재 로그인하여 질문을 전송한 사용자 ID

    Returns:
        list[Chat]: 시간 순서대로(과거 -> 최근) 정렬된 최근 대화 엔티티 목록 (최대 5개)
    """
    statement = (
        select(Chat)
        .where(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc(), Chat.id.desc())
        .limit(5)
    )
    chats = list(db.scalars(statement))
    # AI에게 대화 문맥을 시간 흐름대로 전달하기 위해 오름차순(오래된 순)으로 반전
    chats.reverse()
    return chats
