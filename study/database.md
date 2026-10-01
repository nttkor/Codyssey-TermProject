# AskMate DB 공부 노트

**기준:** `fix/qa-findings` / `baa13d5` (PR #36 반영 완료). 코드 경로는 `backend/` 기준입니다. 인증은 [backend.md](backend.md), 전체 호출 순서는 [flow.md](flow.md)를 참고해 주세요.

## 1. SQLite와 SQLAlchemy의 역할

SQLite는 데이터를 파일에 저장하는 관계형 DB입니다. 일반적인 별도 DB 서버 설치 없이 앱이 파일을 열어 사용합니다. 기본 파일은 `backend/data/askmate.db`입니다.

SQLAlchemy는 Python에서 DB를 연결하고 SQL을 구성하며 객체와 테이블을 연결하는 라이브러리입니다. SQLite 대신 데이터를 저장하는 별도 DB가 아닙니다.

```text
Python User / Chat 객체
  → SQLAlchemy ORM
  → SQL 명령
  → SQLite
  → DB 파일
```

ORM은 객체와 관계형 테이블을 대응시키는 방법입니다. 객체를 `add()`한다고 즉시 영구 저장이 완료되는 것은 아닙니다. `flush()`와 `commit()`의 차이를 함께 이해해야 합니다.

## 2. 코드 지도

| 파일 | 중심 항목 | 역할 |
| --- | --- | --- |
| `app/config.py:16~18` | `DATABASE_PATH` | DB 파일 경로 계산 |
| `app/db_connect.py:21~30` | `engine`, `SessionLocal`, `Base` | 연결과 ORM 기반 |
| `app/db_connect.py:33~37` | `enable_foreign_keys()` | 연결마다 외래 키 검사 활성화 |
| `app/db_connect.py:40~63` | `check_connection()`, `get_db()`, `init_db()` | 연결 확인·요청 세션·테이블 준비 |
| `app/models/user.py:11~20` | `User` | 사용자 테이블 |
| `app/models/chat.py:11~21` | `Chat` | 대화 테이블 |
| `app/account_db.py:10~31` | 저장·사용자명 조회·ID 조회 | 계정 데이터 접근 |
| `app/chat_db.py:10~44` | 저장·전체 조회·최근 5쌍 조회 | 대화 데이터 접근 |
| `app/history.py:37~59` | `get_my_chats()` | 조회 결과를 API 응답으로 변환 |
| `scripts/check_logs.sql:3~6` | 사용자별 SELECT | 확인용 SQL |

API 파일은 인증·오류 안내를 결정하고, DB 함수는 데이터 작업을 맡습니다. DB 함수에서 오류를 숨기지 않고 호출자에게 전달하여 어느 작업이 실패했는지 API에서 설명할 수 있게 합니다.

## 3. 테이블 관계

```text
users
  id ───────────────────────┐
  username                  │ 1명에게 여러 대화
  password_hash             ▼
  created_at              chats
                            id
                            user_id → users.id
                            question
                            answer
                            created_at
```

### users

| 필드 | 모델 정의 | 의미 |
| --- | --- | --- |
| `id` | 정수 기본 키 | 계정 식별자 |
| `username` | `String(30)`, `unique=True` | 정규화된 사용자명 |
| `password_hash` | `Text` | 원본이 아닌 비밀번호 해시 |
| `created_at` | `DateTime`, UTC 기본값 | 계정 생성 시각 |

### chats

| 필드 | 모델 정의 | 의미 |
| --- | --- | --- |
| `id` | 정수 기본 키 | 대화 한 쌍의 식별자 |
| `user_id` | `ForeignKey("users.id")`, `index=True` | 대화 소유자 |
| `question` | `Text` | 사용자 질문 |
| `answer` | `Text` | 성공한 AI 답변 |
| `created_at` | `DateTime`, UTC 기본값 | 대화 행 생성 시각 |

현재는 질문·답변을 별도 메시지 행으로 나누지 않고 한 행에 한 쌍을 저장합니다. 대화방 테이블, 메시지 역할 열, AI 실패 이력 열은 없습니다. 실패 원인은 운영 로그에 남고, 실패 질문은 정상 대화로 저장하지 않습니다.

## 4. 기본 키·고유 제약·외래 키·인덱스

### 기본 키

행을 유일하게 식별합니다. 화면의 몇 번째 카드인지와는 다릅니다. `id`가 같으면 같은 테이블의 같은 기록을 가리킵니다.

### 고유 제약

`users.username`의 중복을 DB가 막습니다. API에서 먼저 “없는 이름인가?” 확인만 해서는 동시에 들어온 두 가입 요청이 모두 통과할 수 있습니다. 최종 DB 고유 제약이 있어야 충돌을 막을 수 있습니다.

사용자명을 소문자로 만드는 것은 `account.py`의 입력 정책입니다. DB가 알아서 모든 문자열을 소문자로 바꾸는 것이 아닙니다. API 경로에서 정규화된 이름을 저장하기 때문에 대소문자만 다른 가입을 중복으로 처리합니다.

`String(30)` 선언만으로 SQLite가 모든 직접 SQL 입력의 30자 제한을 보장한다고 생각하면 안 됩니다. 현재 길이·문자 규칙은 Pydantic 서버 검증에서 중요한 역할을 합니다.

### 외래 키

`chats.user_id`가 존재하는 `users.id`를 가리키도록 제한합니다. SQLite는 연결별 설정이 중요하여 `enable_foreign_keys():33~37`에서 `PRAGMA foreign_keys=ON`을 실행합니다.

모델에는 자동 연쇄 삭제 정책이 정의되어 있지 않습니다. 사용자 삭제 API도 현재 없습니다. `ForeignKey`가 있다고 로그인 인증이나 자동 기록 삭제까지 제공되는 것은 아닙니다.

### 인덱스

`Chat.user_id`의 `index=True`는 사용자별 필터를 돕는 탐색 구조를 만듭니다. 책의 색인처럼 찾는 범위를 줄일 수 있지만, 저장 시 색인 갱신 비용이 추가됩니다. 모든 쿼리가 항상 O(1)이 되는 것은 아닙니다.

현재 선언은 사용자 ID 단일 인덱스입니다. `(user_id, created_at, id)` 복합 인덱스가 있다고 설명하면 안 됩니다. 기록이 커지면 필터·정렬의 실행 계획과 페이지네이션을 검토할 수 있습니다.

## 5. Engine·Session·로그인 세션의 차이

### Engine

`db_connect.py:21~25`의 `engine`은 DB URL과 연결 자원을 관리합니다. 앱 전체에서 재사용합니다. 아직 사용할 세션을 만들기 전부터 준비할 수 있습니다.

### SQLAlchemy Session

`SessionLocal = sessionmaker(bind=engine)`은 세션 생성기를 준비합니다. `get_db():52~55`가 요청별 세션을 만들고 사용 후 닫습니다. ORM 객체의 변경을 모으고 트랜잭션을 처리하는 작업 공간이라고 생각하시면 됩니다.

### 로그인 세션

로그인 세션은 `request.session`과 쿠키의 인증 상태입니다. DB 세션과 이름만 비슷하고 역할·수명·저장 방식이 다릅니다.

```text
로그인 세션: 이 브라우저가 어느 사용자로 로그인했는가?
DB 세션: 이 요청에서 어떤 DB 작업을 수행하고 확정하는가?
```

`check_same_thread=False`는 SQLite 연결의 기본 스레드 제한을 풀어 이 앱의 동기·스레드 풀 사용을 가능하게 합니다. **하나의 ORM 세션을 여러 스레드에서 동시에 써도 안전하다는 허가는 아닙니다.** 요청 간 독립 세션과 작업 순서를 유지해야 합니다.

## 6. 테이블 준비와 기존 DB

`init_db():58~63`는 모델을 가져온 뒤 `Base.metadata.create_all()`을 호출합니다. ORM 클래스가 등록되어야 생성할 테이블 정보를 알 수 있습니다.

```text
check_connection()
  → DB 부모 디렉터리 준비
  → 연결 열기
  → SELECT 1
create_all()
  → 아직 없는 테이블 생성
```

기존 사용자·대화를 삭제하지 않습니다. 서버 재시작 후에도 같은 파일을 열면 기록이 유지됩니다. 다만 기존 테이블의 열 추가·변경까지 처리하는 기능은 아닙니다. 운영 스키마 변경에는 별도 마이그레이션 전략이 필요합니다.

## 7. 저장: add·flush·commit·rollback

사용자 저장과 대화 저장은 같은 패턴입니다.

```text
create_user() 또는 create_chat()
  ├─ 모델 객체 생성
  ├─ db.add(): 세션에 새 객체 등록
  ├─ db.flush(): INSERT를 DB에 보내기, 생성 ID 읽기
  ├─ ID를 지역 변수에 보관
  ├─ db.commit(): 트랜잭션 확정
  ├─ 실패 → db.rollback(): 미확정 변경 취소, 세션 정리
  └─ 성공 → ID 반환
```

위치: `account_db.py:10~21`, `chat_db.py:10~21`입니다.

- `add()`는 저장 후보 등록이지 저장 완료가 아닙니다.
- `flush()`는 SQL을 실행하지만 아직 트랜잭션 확정 전입니다. ID를 얻었다고 성공 반환하면 안 됩니다.
- `commit()`까지 성공해야 저장이 확정됩니다.
- `rollback()`은 실패한 트랜잭션을 되돌리고 세션이 실패 상태에 머무르지 않도록 합니다.
- 지역 변수에 ID를 보관하면 commit 후 ORM 속성 접근으로 추가 조회가 발생하는 상황을 피하는 데 도움이 됩니다.

트랜잭션은 관련 변경을 성공하면 확정하고 실패하면 취소하는 경계입니다. 현재 함수는 각각 한 행을 저장하지만, 원리는 여러 행의 작업에도 적용됩니다.

`create_chat()`은 AI 호출까지 되돌릴 수는 없습니다. AI 외부 호출이 이미 성공한 뒤 DB commit이 실패하면 DB 작업은 취소되지만 외부 AI 호출과 비용은 되돌아가지 않습니다.

## 8. 사용자 조회

### 사용자명으로 조회

`account_db.get_user_by_username():24~26`은 다음 의미의 쿼리를 구성합니다.

```sql
SELECT * FROM users WHERE username = :username;
```

결과가 있으면 `User`, 없으면 `None`입니다. SQLAlchemy `select(User).where(...)`는 SQL 문자열을 직접 이어 붙이는 대신 조건과 값을 분리해서 처리합니다.

### ID로 조회

`get_user_by_id():29~31`는 `db.get(User, user_id)`를 사용합니다. 기본 키 조회이며 세션이 이미 가진 객체를 활용할 수 있습니다. 로그인 쿠키의 ID에 대응하는 계정이 실제 남아 있는지 확인하는 데 쓰입니다.

## 9. 본인 전체 기록 조회

`chat_db.get_chats_by_user():24~31`은 다음 의미입니다.

```sql
SELECT * FROM chats
WHERE user_id = :user_id
ORDER BY created_at DESC, id DESC;
```

`where`는 본인 기록만 선택합니다. `DESC`는 최신 값부터라는 뜻입니다. 같은 시각의 여러 행은 `id DESC`로 순서를 안정적으로 정합니다.

API는 쿼리 문자열의 임의 `user_id`가 아니라 `get_current_user()`의 `user.id`를 전달합니다(`history.py:40~45`). 외래 키는 데이터 관계를 보호하고, 인증 결과 필터는 사용자별 접근을 보호합니다. 둘을 혼동하면 안 됩니다.

현재 함수는 모든 본인 기록을 `list()`로 읽습니다. 페이지 번호·개수 제한이 없으므로 데이터가 커지면 조회량·JSON 크기·카드 렌더링 비용이 증가합니다.

## 10. AI용 최근 5쌍 조회

`get_recent_chats_by_user():34~44`는 최신순으로 `LIMIT 5`에 해당하는 쿼리를 실행한 뒤 Python에서 뒤집습니다.

```text
필터 → 최신순 정렬 → 5개 선택 → reverse()
```

처음부터 오래된 순서로 5개만 고르면 최근 5개가 아니라 가장 오래된 5개가 됩니다. 그래서 “선택할 때 최신순, 사용할 때 시간순”을 분리합니다.

이 제한은 조회·AI 문맥에만 적용됩니다. 6번째 대화를 저장했다고 가장 오래된 기록을 삭제하는 기능은 없습니다. 전체 기록은 누적됩니다.

## 11. UTC 저장과 시간대

모델은 `datetime.now(UTC).replace(tzinfo=None)`를 사용합니다. UTC 시각으로 계산한 뒤 SQLite 저장값에서 시간대 정보를 제거합니다. 이것은 컴퓨터 로컬 시간으로 변환한 것이 아닙니다.

```text
모델 생성: UTC 시각
  → SQLite: 시간대 정보 없는 UTC 값
  → history.py: replace(tzinfo=UTC)
  → JSON: UTC 표시가 있는 날짜 문자열
  → history.js: 브라우저 로컬 시각으로 표시
```

위치: `models/user.py:17~20`, `models/chat.py:18~21`, `history.py:50~57`, `static/js/history.js:59~66`입니다.

`replace(tzinfo=UTC)`는 저장값이 원래 UTC라는 전제에서 시간대 표식을 붙입니다. 임의의 로컬 시각을 UTC로 변환하는 메서드가 아닙니다. 직접 SQL로 기록을 넣는 경우에도 UTC 규칙을 지켜야 합니다.

대화 생성 시각은 질문 전송 시각과 동일한 필드가 아닙니다. 현재는 AI 답변 이후 대화 행이 만들어질 때 기본값이 적용됩니다.

## 12. 읽기 전용 확인 SQL

기존 `scripts/check_logs.sql`은 `:user_id` 매개변수를 요구합니다. SQLite CLI에서 읽기 전용으로 확인하는 예시는 다음과 같습니다. **이번 작성 작업에서는 실행하지 않았습니다.** 운영 DB·실제 개인정보 대신 학습용 로컬 DB를 사용해 주세요.

`B7-1/backend/`에서 시작합니다.

```bash
sqlite3 -readonly data/askmate.db
```

SQLite 프롬프트에서 실행합니다.

```sql
.headers on
.mode column
.parameter init
.parameter set :user_id 1
.read scripts/check_logs.sql
.quit
```

CLI의 `.parameter` 명령이 지원되는 버전인지 확인해 주세요. 사용자 ID 1은 예시이므로 실제 학습용 ID를 지정해야 합니다. SQL에는 로그인 검사가 없고 파일에 접근할 수 있는 사람이 내용을 읽으므로 DB 파일 자체의 접근 권한도 중요합니다.

테이블 구조와 사용자별 건수를 읽는 예시입니다.

```sql
PRAGMA table_info(users);
PRAGMA table_info(chats);
SELECT user_id, COUNT(*) AS chat_count
FROM chats
GROUP BY user_id;
```

평가 증빙에는 필요한 필드만 사용하고 비밀번호 해시·대화 개인정보를 공개하지 마세요. DB 파일 삭제로 초기화하는 방법은 이 노트에서 권장하지 않습니다.

## 13. 동시성·영속성·운영 한계

- SQLite는 동시 읽기와 쓰기에 제약이 있으므로 동기 코드와 스레드 풀을 사용한다고 무제한 동시 쓰기가 되는 것은 아닙니다.
- 요청별 세션은 서로의 변경 상태를 섞지 않도록 돕지만 DB 잠금 충돌 가능성 자체를 없애지는 않습니다.
- 같은 사용자의 질문 두 개가 동시에 처리되면 둘 다 새 답변 저장 전의 문맥을 읽을 수 있습니다. 사용자별 서버 직렬화 기능은 없습니다.
- AI 답변 길이에 대한 별도의 저장 제한은 현재 없습니다.
- Docker에서는 기본 DB 경로가 `/app/data/askmate.db`에 대응하고 `askmate-data` 볼륨으로 유지합니다. 다른 경로를 지정하면 볼륨 범위도 확인해야 합니다.
- 볼륨은 컨테이너와 저장 수명을 분리하지만 백업 자체는 아닙니다. 컨테이너 롤백도 DB를 과거 상태로 복원하지 않습니다.

현재 구현 범위와 장기 운영에서 추가 검토할 점을 나누어 설명하는 것이 좋습니다.

## 14. 테스트에서 볼 근거

| 확인할 테스트 | 의미 |
| --- | --- |
| `test_signup.py::test_duplicate_username_is_case_insensitive` | 사용자명 정규화와 중복 방지 |
| `test_signup.py::test_duplicate_rolls_back_and_session_can_be_reused` | 중복 실패 후 세션 복구 |
| `test_chat_storage.py::test_chat_owner_comes_from_session` | 인증 결과로 소유자 결정 |
| `test_chat_storage.py::test_foreign_key_failure_rolls_back_and_session_can_be_reused` | 외래 키 실패 처리 |
| `test_chat_context.py::test_context_contains_only_latest_five_own_pairs` | 본인 최근 5쌍 선택 |
| `test_chat_context.py::test_context_orders_by_time_then_id_before_forwarding` | 문맥 정렬 기준 |
| `test_chat_history.py::test_history_returns_only_own_records_in_stable_latest_order` | 본인 기록 최신순 |
| `test_chat_history.py::test_verification_sql_filters_users_and_matches_api_order` | 확인 SQL과 API 기준 일치 |

테스트 이름은 `B7-1/backend/tests/`의 해당 파일에서 검색하시면 됩니다. 이 표는 테스트의 의도를 안내하며 이번 세션의 실행 결과를 뜻하지 않습니다.

## 15. 설명 연습과 참고 개념

- DB 세션과 로그인 세션을 각각 한 문장으로 설명해 주세요.
- `flush()` 성공 후 `commit()`이 실패하면 저장 성공으로 반환해도 되나요?
- 사용자명 중복 확인에 DB 고유 제약이 필요한 이유는 무엇인가요?
- 외래 키가 있어도 사용자별 인증 필터가 필요한 이유는 무엇인가요?
- 최신 5쌍 제한이 기록 삭제가 아니라는 점을 설명해 주세요.
- 시간대 없는 값을 UTC로 해석하려면 어떤 전제가 필요한가요?

추가 학습 링크:

- [SQLAlchemy ORM 시작](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [SQLAlchemy Session 기초](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [SQLite 외래 키](https://www.sqlite.org/foreignkeys.html)
- [SQLite CLI](https://www.sqlite.org/cli.html)
