# B7-1 AskMate 기능별 호출 흐름

사용자 입력부터 어떤 함수가 호출되고 어떤 데이터가 바뀌며 무엇이 반환되는지 정리합니다. 정상 흐름뿐 아니라 실패, 접근 제어, 화면 보조 기능, 시작·종료·배포 흐름을 포함합니다.

**기준:** `fix/qa-findings` / `9e3038b`. 아래 코드 경로는 별도 표시가 없으면 `B7-1/backend/` 기준입니다. 실제 파일은 이 문서에서 `../B7-1/backend/` 아래에 있습니다. 라인 번호보다 함수명을 우선해서 찾아 주세요.

## 0. 전체 연결

```text
브라우저 화면
  ├─ GET /login, /signup, /chat, /history
  │    → pages.py → Jinja2 HTML
  ├─ GET /static/... → StaticFiles
  └─ JavaScript apiRequest()
       → JSON API
            ├─ account.py → security.py / account_db.py
            ├─ llm.py → chat_db.py / llm_connect.py
            └─ history.py → chat_db.py
                                 │
                                 ▼
                          db_connect.py
                          SQLAlchemy → SQLite
```

공통 관문은 `main.py:47~60`의 앱·미들웨어·라우터 등록과 `auth.py`의 인증·POST 헤더 검사입니다. `prefix="/api"`가 붙으므로 라우터에 `/chat`이라고 적혀 있어도 최종 API 주소는 `/api/chat`입니다.

## 1. 서버 시작과 종료

입력은 `backend/`에서 실행하는 `uv run uvicorn app.main:app --reload`입니다.

```text
Uvicorn이 app.main:app 가져오기
  ├─ config.py 모듈 로딩
  │    ├─ backend/.env 읽기, 실행 환경 값 우선
  │    ├─ DB 경로 계산
  │    └─ 세션·AI 설정 검증
  ├─ logger.py → 콘솔·app.log 핸들러 설정
  ├─ db_connect.py → engine / SessionLocal 준비
  ├─ llm_connect.py → 비동기 AI 클라이언트 준비
  ├─ FastAPI 앱·미들웨어·라우터 준비
  └─ main.lifespan()
       ├─ init_db()
       │    ├─ 모델 가져오기 → Base.metadata에 테이블 등록
       │    ├─ check_connection() → 디렉터리 준비 → SELECT 1
       │    └─ create_all() → 없는 테이블 생성
       ├─ 시작 로그
       ├─ yield → 요청 처리 기간
       └─ 종료 시 finally → engine.dispose()
```

확인 위치: `app/config.py:10~54`, `app/config_validation.py:7~15`, `app/main.py:34~60`, `app/db_connect.py:40~63`입니다.

설정이 없거나 잘못되면 앱이 시작하지 않습니다. 연결 실패도 시작 단계에서 드러납니다. `create_all()`은 기존 테이블 구조를 자동 변경하는 마이그레이션이 아닙니다.

## 2. 화면 접근과 이동

| 요청 | 중심 함수 | 결과 |
| --- | --- | --- |
| `GET /` | `pages.index():17~19` | 307로 `/login` 이동 |
| `GET /login` | `pages.login_page():22~26` | 비로그인이면 HTML, 로그인했으면 303으로 `/chat` |
| `GET /signup` | `pages.signup_page():29~33` | 비로그인이면 HTML, 로그인했으면 303으로 `/chat` |
| `GET /chat` | `pages.chat_page():36~42` | 비로그인이면 303으로 `/login`, 로그인했으면 HTML |
| `GET /history` | `pages.history_page():45~51` | 위와 같은 접근 제어 |

로그인 상태 확인이 필요한 화면은 다음 공통 흐름을 사용합니다.

```text
브라우저 쿠키
  → SessionMiddleware가 서명·유효기간 확인
  → request.session
  → auth.get_session_user()
       ├─ user_id 없음 → None
       ├─ user_id 있음 → account_db.get_user_by_id()
       │    ├─ 계정 있음 → User 객체
       │    └─ 계정 없음 → 세션 비우기 → None
       └─ DB 조회 실패 → 500
  → pages.py에서 HTML 반환 또는 리다이렉트
```

확인 위치: `app/main.py:48~55`, `app/auth.py:26~38`, `app/account_db.py:29~31`입니다. 로그인 화면 이동과 API의 401 응답은 서로 다른 정책입니다.

HTML이 내려온 뒤 `templates/base.html:7~9`의 CSS·공통 JS와 각 화면의 전용 JS를 로드합니다. `defer` 스크립트와 `DOMContentLoaded`가 DOM 준비 후 이벤트 등록을 돕습니다.

## 3. 공통 API 요청

```text
화면별 이벤트 핸들러
  → common.js: apiRequest(url, options)
       ├─ Content-Type: application/json 준비
       ├─ GET/HEAD 외 요청에 X-Requested-With 추가
       ├─ 객체 body를 JSON.stringify()
       ├─ fetch()
       ├─ 401이며 예외 옵션 없음 → /login 이동
       ├─ 204 → JSON 파싱 없이 data: null
       ├─ JSON 응답이면 response.json()
       └─ {ok, status, data} 반환
            네트워크·파싱 예외 → ok: false, status: 0
```

확인 위치: `app/static/js/common.js:7~61`, `getErrorMessage():64~71`입니다. `status: 0`은 서버가 보낸 HTTP 코드가 아니라 프론트에서 만든 실패 표시입니다. HTTP 500 등은 `fetch()`의 예외가 아니라 `response.ok === false`로 처리합니다.

로그인과 로그아웃은 `skipAuthRedirect: true`로 공통 401 이동을 건너뛰고 직접 결과를 처리합니다. 같은 출처의 기본 `fetch()`이므로 쿠키를 브라우저가 함께 전송합니다.

## 4. 회원가입

입력 예시는 사용자명 `Study_User`와 길이 조건을 만족하는 학습용 비밀번호입니다.

```text
signup.html의 signupForm 제출
  → signup.js의 submit 핸들러
       ├─ preventDefault(): 기본 폼 이동 막기
       ├─ 사용자명 trim() → 소문자
       ├─ 사용자명·비밀번호 길이·비밀번호 확인 검사
       ├─ 실패 → 안내, 포커스 → 요청 없음
       ├─ 제출 버튼 잠금·처리 중 표시
       └─ apiRequest(POST /api/signup, {username, password})
            → require_csrf_header()
            → SignUpPayload 서버 검증
            → account.signup()
                 ├─ security.hash_password()
                 ├─ account_db.create_user()
                 │    ├─ User 생성 → add()
                 │    ├─ flush() → 생성 ID 확보
                 │    ├─ commit()
                 │    └─ 실패 → rollback() → 예외 전달
                 └─ 201 {id, username}
            → 성공 안내
            → 약 600ms 뒤 /login?registered=1 이동
```

상태 변화는 `users` 행 추가입니다. **로그인 쿠키는 발급하지 않습니다.** 비밀번호 확인 값은 프론트 검사용이며 서버에 보내지 않습니다.

| 확인할 코드 | 함수 또는 라인 |
| --- | --- |
| 폼과 입력 요소 | `app/templates/signup.html:13~73` |
| 실시간 비밀번호 확인 | `app/static/js/signup.js:18~36`, `checkPasswordMatch()` |
| 제출·검증·API·이동 | `app/static/js/signup.js:38~107` |
| 요청 모델 | `app/account.py:31~45`, `Username`, `SignUpPayload` |
| 가입 API | `app/account.py:59~80`, `signup()` |
| 비밀번호 해시 | `app/security.py:8~10`, `hash_password()` |
| DB 저장 | `app/account_db.py:10~21`, `create_user()` |

중복 사용자명은 DB 고유 제약으로 확인하고 409를 반환합니다. 다른 DB 오류는 500입니다. 서버 입력 검증 실패는 422이며 원본 비밀번호는 응답에서 제외합니다. `Study_User`와 `study_user`는 같은 정규화된 이름입니다.

## 5. 로그인과 가입 완료 안내

```text
login.js 초기화
  └─ URLSearchParams로 registered=1 확인 → 가입 완료 안내

loginForm 제출
  → login.js submit 핸들러
       ├─ 사용자명 trim(), 비밀번호 원본 유지
       ├─ 빈 값이면 안내 → 요청 없음
       ├─ 버튼 잠금·처리 중 표시
       └─ apiRequest(POST /api/login, skipAuthRedirect: true)
            → 헤더 검사·LoginPayload 검증
            → account.login()
                 ├─ get_user_by_username()
                 ├─ verify_password()
                 ├─ 실패 → 401, 기존 세션 변경 없음
                 ├─ 성공 → request.session.clear()
                 ├─ request.session["user_id"] = user.id
                 └─ 200 {id, username}, Cache-Control: no-store
            → SessionMiddleware가 세션 쿠키 발급
            → 성공하면 브라우저 /chat 이동
            → 실패하면 메시지·버튼 복구·비밀번호 칸 비우기
```

확인 위치: `app/static/js/login.js:15~62`, `app/account.py:48~51,83~105`, `app/security.py:13~15`, `app/main.py:48~55`입니다.

`account.login()`이 직접 쿠키 문자열을 만들지는 않습니다. 세션에 값을 넣으면 미들웨어가 응답 쿠키를 처리합니다. 로그인은 DB 행 추가가 아니라 계정 조회와 브라우저 인증 상태 변경입니다.

## 6. 현재 사용자 조회

```text
GET /api/me
  → auth.get_current_user()
       → get_session_user() → 세션의 ID로 DB 사용자 확인
       ├─ 없음 → 401
       └─ 있음 → User 객체
  → account.me()
       ├─ Cache-Control: no-store
       └─ 200 {id, username}
```

확인 위치: `app/account.py:108~112`, `app/auth.py:26~45`입니다. 비밀번호 해시는 반환하지 않습니다. 현재 네비게이션 이름은 이 API를 호출해서 넣는 것이 아니라 Jinja2의 `user.username`으로 렌더링합니다(`templates/base.html:19~27`).

## 7. 채팅 입력 보조 기능

확인 위치는 `app/static/js/chat.js`입니다.

| 사용자 행동 | 호출 흐름 | 결과 |
| --- | --- | --- |
| 입력 변경 | `input` → `updateCharCounter():29~45` | 글자 수, 버튼 활성화, 입력창 높이 갱신 |
| 일반 Enter | `keydown:60~69` → 기본 동작 막기 → submit 이벤트 | 활성 상태이면 전송 |
| Shift+Enter | 같은 keydown 분기 | 전송하지 않고 줄바꿈 |
| 한글 조합 확정 Enter | `compositionstart/end:56~57`, 조합 검사 `62` | 조합 입력 중 전송 방지 |
| 추천 질문 클릭 | `.quick-chip` 클릭 `72~80` | 입력창에 질문만 넣고 포커스, 자동 전송 없음 |
| 오류 배너 닫기 | 클릭 `83~87` | 배너만 숨김 |

조합 상태는 `isComposing`, 이벤트의 `isComposing`, `keyCode === 229`를 함께 확인합니다. 한글 글자 확정 Enter와 질문 전송 Enter를 구분하기 위한 처리입니다.

## 8. 질문 → AI 응답 → 대화 저장

```text
chatForm submit
  → chat.js:166~227
       ├─ trim(), 빈 질문·길이·isSubmitting 검사
       ├─ isSubmitting=true, 버튼·입력창 잠금
       ├─ appendMessage("user", question): 화면에 질문 추가
       ├─ 입력창 비우기
       ├─ showLoadingBubble()
       └─ apiRequest(POST /api/chat, {question})
            → require_csrf_header()
            → 로그인 사용자·DB 세션 의존성 해결, ChatRequest 검증
            → llm.chat()
                 ├─ request_received 로그
                 ├─ run_in_threadpool(get_recent_chats_by_user, db, user.id)
                 │    ├─ 본인 기록 최신순 최대 5개 선택
                 │    └─ reverse() → 오래된 순서
                 ├─ 각 기록을 user / assistant 메시지 두 개로 펼치기
                 ├─ await llm_connect.generate_answer(question, history)
                 │    ├─ _build_messages(): 과거 메시지 뒤 현재 질문 추가
                 │    ├─ ai_call_started 로그
                 │    ├─ AsyncOpenAI.chat.completions.create()
                 │    ├─ choices/message/content 확인
                 │    ├─ 답변 trim(), 비어 있지 않은 문자열 확인
                 │    └─ ai_call_success 로그 → 답변 문자열 반환
                 ├─ run_in_threadpool(create_chat, db, user.id, question, answer)
                 │    └─ add → flush → commit
                 ├─ db_save_success 로그
                 └─ 200 {"answer": answer}
       ├─ hideLoadingBubble()
       ├─ appendMessage("ai", answer)
       ├─ lastFailedQuestion 초기화
       └─ 버튼·입력창 잠금 해제, 포커스
```

입력은 질문 문자열 하나입니다. 브라우저가 사용자 ID나 문맥을 정하지 않습니다. 실제 소유자는 인증 결과인 `user.id`에서 얻습니다.

| 단계 | 핵심 코드 |
| --- | --- |
| 제출·말풍선·로딩 | `app/static/js/chat.js:102~163,166~227` |
| 서버 질문 모델 | `app/llm.py:38~41`, `ChatRequest` |
| 파이프라인 | `app/llm.py:44~92`, `chat()` |
| 문맥 조회 | `app/chat_db.py:34~44`, `get_recent_chats_by_user()` |
| AI 메시지 구성 | `app/llm_connect.py:46~49`, `_build_messages()` |
| AI 호출·응답 확인 | `app/llm_connect.py:52~108`, `generate_answer()` |
| 저장 | `app/chat_db.py:10~21`, `create_chat()` |

성공하면 `chats`에 질문·답변 한 쌍이 추가됩니다. 말풍선은 DB보다 먼저 바뀌므로 화면에 질문이 있어도 저장 성공이라고 단정할 수 없습니다.

## 9. 문맥 구성 예시

DB에 오래된 순서로 Q1/A1부터 Q7/A7까지 있다면 다음 질문 Q8의 AI 입력은 다음과 같습니다.

```text
최신순 조회: Q7/A7, Q6/A6, Q5/A5, Q4/A4, Q3/A3
reverse():  Q3/A3, Q4/A4, Q5/A5, Q6/A6, Q7/A7
messages:
  user Q3, assistant A3,
  user Q4, assistant A4,
  user Q5, assistant A5,
  user Q6, assistant A6,
  user Q7, assistant A7,
  user Q8
```

과거 기록이 5쌍이면 총 11개 메시지입니다. 0쌍이면 현재 질문 1개만 전달합니다. 현재 질문은 `_build_messages()`에서 한 번 추가하며, 저장은 응답 이후입니다.

로그아웃 후 같은 계정으로 다시 로그인해도 DB 기록이 남으므로 문맥에 쓰일 수 있습니다. 대화방 ID, 초기화 API, 토큰 수에 따른 문맥 제한은 현재 구현에 없습니다.

## 10. 채팅 실패와 재시도

| 실패 지점 | 서버 결과 | AI 호출·DB 변화 | 화면 처리 |
| --- | --- | --- | --- |
| POST 헤더 없음·잘못됨 | 403 | 채팅 함수 진입 안 함 | 안내, AI 재시도 버튼 숨김 |
| 비로그인 | 401 | AI 호출·대화 저장 없음 | `/login` 이동 |
| 질문 검증 실패 | 422 | AI 호출·대화 저장 없음 | 안내 |
| 최근 기록 조회 실패 | 500 | AI 호출·대화 저장 없음 | 안내 |
| AI 시간 초과 | 504 | 대화 저장 안 함 | 안내·재시도 버튼 |
| AI 서비스 오류·잘못된 답변 | 502 | 대화 저장 안 함 | 안내·재시도 버튼 |
| AI 성공 후 DB 저장 실패 | 500 | 저장 함수 rollback | 안내, 답변 말풍선 없음 |
| 브라우저 통신·파싱 예외 | 프론트 내부 status 0 | 서버 처리 결과는 단정 불가 | 오류 안내 |

핵심 분기는 `app/llm.py:53~90`, `app/llm_connect.py:65~103`, `app/static/js/chat.js:196~226`입니다. 정의된 AI 예외를 처리하는 것이며, 모든 종류의 예상 밖 프로그래밍 오류를 이 분기가 잡는 것은 아닙니다.

```text
502 또는 504
  → lastFailedQuestion에 질문 보관
  → 다시 시도 버튼 클릭 (chat.js:90~99)
       ├─ 보관한 질문을 입력창에 복원
       ├─ 배너 숨김
       └─ submit 이벤트 → 새로운 API 요청
```

재시도는 기존 요청을 이어받는 것이 아닙니다. 새 말풍선과 새 요청이 생깁니다. 요청 ID 기반 중복 방지 기능은 없으므로 네트워크 실패만 보고 서버 저장 여부를 확정할 수 없습니다. UI 중복 제출 잠금은 현재 화면에만 적용됩니다.

## 11. 대화 기록 조회·새로고침·재조회

```text
GET /history → 로그인 확인 → history.html
  → history.js DOMContentLoaded
       → fetchHistory()
            ├─ 로딩 표시, 목록·빈 상태·오류 숨김
            └─ apiRequest(GET /api/me/chats)
                 → get_current_user()
                 → history.get_my_chats()
                      ├─ get_chats_by_user(db, user.id)
                      │    └─ 본인 기록, created_at DESC / id DESC
                      ├─ DB UTC 시각에 UTC 정보 붙이기
                      ├─ Cache-Control: no-store
                      └─ 200 [{id, question, answer, created_at}, ...]
            ├─ 401 → /login
            ├─ 실패 → 오류·재조회 버튼
            ├─ 빈 배열 → 빈 기록 안내
            └─ 기록 있음
                 ├─ 총 개수 표시
                 ├─ 기존 목록 지우기
                 ├─ 시각을 브라우저 로컬 시간으로 표시
                 └─ 질문·답변 카드 생성, textContent 사용
```

확인 위치: `app/static/js/history.js:19~115`, `app/history.py:30~59`, `app/chat_db.py:24~31`, `app/templates/history.html:20~46`입니다.

새로고침·다시 불러오기 버튼은 같은 `fetchHistory()`를 실행합니다(`history.js:117~121`). 화면의 `#번호`는 `chats.length - index`로 만든 표시 번호이며 실제 DB `id`가 아닙니다(`history.js:71~72`).

“새 대화 시작”은 `history.html:16`의 `/chat` 링크입니다. 기록 삭제나 문맥 초기화가 없습니다. `/chat` 화면은 예전 DB 기록을 말풍선으로 복원하지 않지만 서버는 여전히 최근 기록을 사용합니다.

## 12. 로그아웃

```text
navLogoutBtn 클릭
  → common.initNavbar()의 클릭 핸들러
       ├─ disabled이면 중복 클릭 무시
       ├─ 버튼 잠금, 기존 오류 숨김
       └─ apiRequest(POST /api/logout, skipAuthRedirect: true)
            → require_csrf_header()
            → account.logout()
                 ├─ 현재 user_id를 로그용으로 읽기
                 ├─ request.session.clear()
                 └─ 204, Cache-Control: no-store
            → 미들웨어가 필요 시 현재 브라우저 세션 쿠키 삭제
       ├─ res.ok && status === 204 → /login 이동
       ├─ 그 외 → 실패 안내, 현재 화면 유지
       └─ finally → 버튼 잠금 해제
```

확인 위치: `app/static/js/common.js:89~115`, `app/account.py:115~122`, `app/templates/base.html:27,38~40`입니다. 이미 비로그인 상태여도 정상 헤더가 있으면 204입니다. DB 계정·대화 행은 삭제하지 않습니다.

서버 측 세션 저장소가 없으므로 **이미 복사된 유효 쿠키를 로그아웃만으로 즉시 폐기하지 못합니다.** 현재 브라우저의 쿠키 삭제와 모든 세션 철회는 다릅니다.

## 13. 비밀번호 표시·숨김

```text
DOMContentLoaded
  → common.initPasswordToggles()
       → .toggle-password 버튼마다 click 등록
            → data-target의 ID로 입력 요소 찾기
            → type="password" ↔ type="text"
```

확인 위치: `app/static/js/common.js:74~86`, `app/templates/login.html:42`, `signup.html:41,60`입니다. 표시 방식만 바꾸며 입력값, DB, 인증 상태는 바꾸지 않습니다.

## 14. 상태 확인·정적 파일·자동 API 문서

- `GET /health` → `app/main.py:73~75`, `health()` → `200 {"status":"ok"}`입니다. DB·AI 점검은 없습니다.
- `GET /static/...` → `app/main.py:56`의 `StaticFiles`가 CSS·JS 파일을 제공합니다.
- `/docs`, `/redoc`, `/openapi.json`은 현재 FastAPI 기본 설정에서 제공하는 API 문서·명세 경로입니다. API 입력·응답 모델과 라우트에서 명세를 생성하며, 문서를 열었다고 로그인되는 것은 아닙니다.
- DB 직접 확인은 `scripts/check_logs.sql:3~6`입니다. `:user_id`를 지정하여 본인 기준과 같은 정렬의 기록을 조회합니다. API와 달리 SQL 자체에는 로그인 인증이 없습니다.

## 15. 공통 검증 오류·로그

```text
Pydantic/FastAPI 요청 검증 실패
  → main.validation_error()
       ├─ 오류마다 type / loc / msg만 선택
       └─ 422 {"detail": [오류 목록]}
  → common.getErrorMessage() → 안내 문구
```

확인 위치: `app/main.py:63~70`입니다. 원본 입력을 포함할 수 있는 `input`, `ctx`를 제외합니다. DB 예외는 서버에서 로그로 기록하고 고정된 사용자 안내만 HTTP 응답으로 반환합니다.

핵심 로그 흐름은 `request_received → ai_call_started → ai_call_success 또는 실패 → db_save_success 또는 실패`입니다. AI 실패라 저장 단계에 도달하지 않으면 DB 저장 로그도 없습니다. 로그 설정은 `app/logger.py:15~40`입니다.

## 16. 자동 배포와 복구 흐름

코드 위치는 `B7-1/.github/workflows/deploy-oci.yml`입니다.

```text
대상 이벤트
  ├─ develop/main 대상 같은 저장소 PR → 실제 게시·배포
  ├─ develop/main 대상 포크 PR → 이미지 빌드만 검증
  ├─ develop/main push → 지정 경로 변경 시 게시·배포
  └─ 수동 실행 → main/develop에서 게시·배포
       → 필수 설정·타임아웃 검증
       → 이미지 태그 결정
       → Docker 이미지 빌드·Docker Hub 게시
       → Tailscale 연결 → SSH 준비
       → 서버에 환경 변수 전달
       → 새 이미지 pull
       → 기존 컨테이너 중지·백업 이름으로 변경
       → DB 볼륨을 연결하여 새 컨테이너 실행
       ├─ healthy → 기존 백업 컨테이너 삭제
       └─ 실행·상태 검사 실패 → rollback() → 기존 컨테이너 재시작
```

위치: 이벤트 `3~18`, 작업 분기 `28~71`, 설정 `93~142`, 태그 `144~179`, 빌드·접속 `181~237`, 환경 전달 `239~259`, 교체·복구 `261~377`입니다. Docker 실행·상태 검사는 `backend/Dockerfile:26~33`을 함께 보세요.

컨테이너 교체는 DB 초기화가 아닙니다. `askmate-data` 볼륨을 `/app/data`에 연결합니다. 이 복구는 컨테이너 버전 복구이며 DB 변경을 되돌리는 기능은 아닙니다. 이번 노트 작성에서는 워크플로를 실행하지 않았습니다.

## 17. 기능과 중심 함수 요약

| 기능 | 중심 함수·핸들러 | 주요 상태 변화 |
| --- | --- | --- |
| 시작·종료 | `main.lifespan()`, `db_connect.init_db()` | 연결·테이블 준비, 종료 시 엔진 정리 |
| 화면 접근 | `pages.*_page()`, `auth.get_session_user()` | 리다이렉트 또는 HTML |
| 회원가입 | `signup.js submit`, `account.signup()`, `create_user()` | 사용자 행 추가 |
| 로그인 | `login.js submit`, `account.login()` | 브라우저 세션 쿠키 발급 |
| 현재 사용자 | `account.me()` | 공개 사용자 정보 반환 |
| 질문 처리 | `chat.js submit`, `llm.chat()`, `generate_answer()` | 화면 말풍선, 성공 시 대화 행 추가 |
| 문맥 유지 | `get_recent_chats_by_user()`, `_build_messages()` | 요청용 메시지 목록 구성 |
| 기록 조회 | `fetchHistory()`, `get_my_chats()` | 기록 카드 렌더링 |
| AI 재시도 | `chat.js retry 클릭` | 이전 질문으로 새 요청 |
| 기록 재조회 | `history.js refresh/retry 클릭` | 목록 다시 조회 |
| 로그아웃 | `initNavbar()`, `account.logout()` | 현재 브라우저 쿠키 삭제 |
| 비밀번호 토글 | `initPasswordToggles()` | 입력 요소 표시 타입 변경 |
| 상태 확인 | `main.health()` | 고정 JSON 반환 |
| 로그 확인 | `check_logs.sql` | 사용자별 저장 기록 읽기 |
| 배포·복구 | 워크플로, 셸 `rollback()` | 이미지·컨테이너 교체 또는 복구 |

## 18. 설명 연습

1. 질문 말풍선이 있는데 DB에는 기록이 없을 수 있는 상황을 설명해 주세요.
2. 로그인 화면에서 401일 때 강제 이동을 건너뛰는 이유를 설명해 주세요.
3. 최신 5개를 조회하면서 AI에는 오래된 순서로 보내는 이유를 설명해 주세요.
4. 같은 사용자가 브라우저 두 개로 질문할 때 문맥과 중복 제출 잠금의 범위를 설명해 주세요.
5. 새 버전 배포에 실패했을 때 무엇을 복구하고 무엇은 복구하지 않는지 설명해 주세요.
