"""
AskMate 사용자 계정 데이터베이스 모델 (User Entity Model)

[파일 개요]
본 모듈은 AskMate 서비스의 가입 회원 정보 및 인증 자격 증명을 영구 저장하는
`users` 테이블의 SQLAlchemy 2.0 ORM 모델을 정의합니다.

[보안 및 기술 설계]
1. 비밀번호 평문 저장 금지:
   - 보안 사고 발생 시에도 비밀번호 원본이 유출되지 않도록 `password_hash` 필드에
     Argon2id로 암호화된 단방향 해시 문자열만 저장합니다.
2. 사용자명 고유성 보장:
   - `username` 컬럼에 UNIQUE 인덱스를 설정하여 동일한 아이디의 중복 가입을
     데이터베이스 레벨에서 원천 방지합니다. (대소문자 정규화는 비즈니스 계층에서 선행)
3. 시간대 처리 (UTC):
   - SQLite는 시간대(Timezone) 정보를 지원하지 않으므로, 서버 운영체제의 로컬 시간대와 무관하게
     항상 UTC 기준으로 나이브한(naive) `datetime` 객체를 저장합니다.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db_connect import Base


class User(Base):
    """사용자 계정 정보를 나타내는 ORM 엔티티 클래스 (`users` 테이블).

    Attributes:
        id (int): 고유 기본 키(Primary Key, Auto-increment 정수).
        username (str): 3~30자의 로그인 아이디 (고유 제약조건 UNIQUE 적용).
        password_hash (str): Argon2id 알고리즘으로 단방향 암호화된 패스워드 해시 문자열.
        created_at (datetime): 계정 생성 시각 (시간대 정보가 제거된 UTC 기준 datetime).
    """

    __tablename__ = "users"

    # 고유 식별자 (자동 증가 정수 기본키)
    id: Mapped[int] = mapped_column(primary_key=True)

    # 로그인용 사용자명 (최대 30자, 중복 불가)
    username: Mapped[str] = mapped_column(String(30), unique=True)

    # Argon2id 해시 문자열 (솔트 및 알고리즘 메타데이터 포함)
    password_hash: Mapped[str] = mapped_column(Text)

    # 계정 생성 일시: SQLite에는 시간대 정보 없이 저장하며, 애플리케이션에서는 항상 UTC로 해석합니다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
