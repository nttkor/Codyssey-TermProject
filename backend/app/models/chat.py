"""
AskMate 대화 기록 데이터베이스 모델 (Chat Entity Model)

[파일 개요]
본 모듈은 사용자가 전송한 질문과 이에 대해 AI가 생성한 답변의 한 쌍(Q&A Pair)을
영구 보관하는 `chats` 테이블의 SQLAlchemy 2.0 ORM 모델을 정의합니다.

[데이터 무결성 및 인덱스 설계]
1. 외래키 제약 (Foreign Key):
   - `user_id` 컬럼은 `users.id`를 참조하여, 등록된 사용자만이 대화 기록을 소유할 수 있도록 보장합니다.
2. 성능 최적화 인덱스:
   - `index=True` 설정을 통해 `user_id`에 B-Tree 인덱스를 생성합니다.
   - 대화 기록 목록 조회(`/api/me/chats`) 및 최근 대화 문맥 조회(최근 5쌍) 시
     사용자별 레코드를 신속하게 필터링할 수 있도록 쿼리 속도를 최적화합니다.
3. 시간대 처리 (UTC):
   - 사용자 테이블과 동일하게 시간대 오프셋이 배제된 UTC 나이브 datetime으로 저장되어
     생성 일시(`created_at`) 및 ID 기준의 정확한 정렬을 보장합니다.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db_connect import Base


class Chat(Base):
    """사용자와 AI 간의 질문·답변 한 쌍을 영구 저장하는 ORM 엔티티 클래스 (`chats` 테이블).

    Attributes:
        id (int): 대화 기록 고유 식별자 (기본 키, Auto-increment).
        user_id (int): 대화의 소유자 사용자 ID (`users.id`를 참조하는 외래키, 인덱스 생성됨).
        question (str): 사용자가 입력한 질문 본문 (Text).
        answer (str): 외부 AI 서비스가 생성한 응답 답변 본문 (Text).
        created_at (datetime): 대화 저장 시각 (시간대 정보가 제거된 UTC 기준 datetime).
    """

    __tablename__ = "chats"

    # 대화 기록 고유 식별자 (기본키)
    id: Mapped[int] = mapped_column(primary_key=True)

    # 대화 소유자 외래키 (사용자별 빠른 조회를 위해 B-Tree 인덱스 부여)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # 사용자의 질문 원문
    question: Mapped[str] = mapped_column(Text)

    # AI 모델이 생성한 답변 텍스트
    answer: Mapped[str] = mapped_column(Text)

    # 대화 저장 일시: SQLite에는 시간대 정보 없이 저장하며, 애플리케이션에서는 항상 UTC로 해석합니다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
