"""
AskMate 데이터베이스 ORM 모델 패키지 (Database ORM Models Package)

[패키지 개요]
본 패키지는 SQLAlchemy 2.0 선언적 매핑(Declarative Mapping) 기반의
데이터베이스 테이블 엔티티 클래스들을 정의합니다.

[포함 모듈]
- `user.py`: 사용자 계정 및 인증 정보(`users` 테이블) 매핑 클래스
- `chat.py`: 사용자별 질문 및 AI 답변 기록(`chats` 테이블) 매핑 클래스

[아키텍처 규칙]
- 모든 모델은 `app.db_connect.Base`를 상속받아 동일한 메타데이터 네임스페이스를 공유합니다.
- 테이블 간 관계는 외래키(ForeignKey)를 명시하여 무결성을 유지하며,
  시간 정보는 SQLite의 특성을 고려하여 UTC 기준 나이브 datetime 형태로 저장합니다.
"""
