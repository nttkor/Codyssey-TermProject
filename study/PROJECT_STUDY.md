# AskMate — 프로젝트 학습 문서 (PROJECT_STUDY.md)

> 이 문서는 `backend/app` 폴더를 분석하여 프로젝트 전체 구조와 각 모듈의 역할을 정리한 학습용 문서입니다.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | AskMate |
| **프레임워크** | FastAPI (Python) |
| **DB** | SQLite (SQLAlchemy ORM) |
| **AI 연동** | OpenAI 호환 API (Chat Completions 형식) |
| **인증 방식** | 서버 세션 (SessionMiddleware) |
| **UI** | Jinja2 템플릿 + 정적 파일 (HTML/CSS/JS) |

---

## 2. 폴더 구조

```
Codyssey-TermProject/
├── backend/
│   ├── app/                    ← 핵심 애플리케이션 코드
│   │   ├── main.py             ← FastAPI 앱 진입점
│   │   ├── config.py           ← 환경변수 로드 및 설정
│   │   ├── config_validation.py← 앱 기동 및 CI 배포 검사 공통 환경변수 검증
│   │   ├── db_connect.py       ← SQLAlchemy 엔진, 세션, Base
│   │   ├── auth.py             ← 세션 인증, CSRF 헤더 검사
│   │   ├── security.py         ← 비밀번호 해시/검증 (Argon2)
│   │   ├── logger.py           ← 로거 설정
│   │   ├── account.py          ← 회원가입·로그인·로그아웃 API
│   │   ├── account_db.py       ← 사용자 DB CRUD
│   │   ├── llm.py              ← AI 채팅 API (질문 → AI → DB 저장)
│   │   ├── llm_connect.py      ← 외부 AI 서비스 통신 모듈
│   │   ├── history.py          ← 대화 기록 조회 API
│   │   ├── chat_db.py          ← 대화 기록 DB CRUD
│   │   ├── pages.py            ← HTML 페이지 라우터 (Jinja2)
│   │   ├── models/
│   │   │   ├── user.py         ← User 테이블 모델
│   │   │   └── chat.py         ← Chat 테이블 모델
│   │   ├── static/
│   │   │   ├── css/style.css
│   │   │   └── js/             ← chat.js, history.js, login.js, common.js 등
│   │   └── templates/          ← base.html, login.html, signup.html, chat.html 등
│   ├── data/                   ← SQLite DB 파일 저장 위치
│   ├── scripts/                ← 유틸리티 스크립트 (check_logs.sql 등)
│   └── tests/                  ← 테스트 코드
│       ├── test_ai_chat.py     ← AI 채팅 및 비정상 응답 복구 검증
│       ├── test_config.py      ← 설정 및 타임아웃 검증
│       └── frontend/           ← Node 내장 테스트 러너 기반 프론트 단위 테스트
│           ├── chat-input.test.cjs ← IME 한글 조합 및 Enter 전송 테스트
│           └── logout.test.cjs     ← 로그아웃 상태코드별 응답 및 재시도 테스트
└── docs/                       ← 프로젝트 문서 (API, DB, TEAM, TESTING 등)
```

---

## 3. 모듈별 역할 상세

### 3-1. `main.py` — 앱 진입점

- `FastAPI` 앱 인스턴스 생성 및 미들웨어/라우터 등록
- **lifespan** 이벤트로 서버 시작 시 DB 초기화(`init_db`), 종료 시 엔진 해제
- **SessionMiddleware** 설정 (쿠키명: `askmate_session`)
- **정적 파일** `/static` 경로로 마운트
- **라우터 등록**:
  | 라우터 | prefix | 역할 |
  |--------|--------|------|
  | `pages_router` | (없음) | HTML 페이지 반환 |
  | `account_router` | `/api` | 회원가입·로그인·로그아웃·현재 사용자 |
  | `llm_router` | `/api` | AI 채팅 |
  | `history_router` | `/api` | 대화 기록 조회 |
- **전역 예외 핸들러**: `RequestValidationError` 처리 시 비밀번호 입력값 숨김
- `GET /health` — 서버 상태 확인 엔드포인트

---

### 3-2. `config.py` & `config_validation.py` — 환경변수 설정 및 검증

`.env` 파일(또는 배포 환경변수)을 읽어 전역 설정을 제공합니다.  
배포 환경변수가 `.env`보다 **우선** 적용됩니다 (`load_dotenv(override=False)`).

| 변수명 | 설명 | 기본값 | 검증 기준 |
|--------|------|--------|-----------|
| `DATABASE_PATH` | SQLite DB 파일 경로 | `data/askmate.db` | 경로 존재 여부 디렉터리 자동 생성 |
| `SESSION_SECRET_KEY` | 세션 암호화 키 (필수) | — | 비어 있으면 시작 실패 |
| `SESSION_MAX_AGE` | 세션 유지 시간(초) | `3600` | 양의 정수 |
| `SESSION_HTTPS_ONLY` | HTTPS 전용 쿠키 여부 | `false` | boolean 변환 |
| `AI_API_KEY` | AI 서비스 API 키 (필수) | — | 비어 있으면 시작 실패 |
| `AI_BASE_URL` | AI 서비스 Base URL (필수) | — | http/https 스킴 검증 |
| `AI_MODEL` | 사용할 AI 모델명 (필수) | — | 비어 있으면 시작 실패 |
| `AI_TIMEOUT` | AI 요청 제한 시간(초) | `30` | `parse_ai_timeout`: 유한한 양수 (`math.isfinite() and > 0`) |

> **엄격한 타임아웃 검증 (`config_validation.py`)**:
> - 표준 라이브러리(`math`, `os`)만 사용하여 의존성 없이 실행 가능.
> - `nan`, `inf`, `-inf`, `1e999`, `0.0`, `-1` 등 무한대/비수/음수 값을 원천 차단.
> - 앱 기동 시점(`config.py`)과 GitHub Actions OCI 배포 사전 검사 스크립트(`.github/workflows/deploy-oci.yml`)에서 동일한 검증 로직을 공유하여 배포와 런타임 간의 설정 불일치를 방지합니다.

---

### 3-3. `db_connect.py` — DB 연결

- SQLite 엔진 생성 (`check_same_thread=False`, `hide_parameters=True`)
- **`Base`**: 모든 테이블 모델의 상위 클래스 (`DeclarativeBase`)
- **`enable_foreign_keys`**: 연결 시 `PRAGMA foreign_keys=ON` 자동 실행
- **`get_db()`**: FastAPI Depends에서 사용하는 요청별 세션 제공 (Generator)
- **`init_db()`**: 서버 시작 시 모든 테이블 자동 생성

---

### 3-4. `auth.py` — 인증 & 보안

| 함수 | 역할 |
|------|------|
| `require_csrf_header()` | POST 요청에 `X-Requested-With: XMLHttpRequest` 헤더 강제 (CSRF 방어) |
| `get_session_user()` | 세션의 `user_id`로 DB 조회, 비로그인 시 `None` 반환 |
| `get_current_user()` | 로그인 필수 API에서 사용, 비로그인 시 **401** 반환 |

---

### 3-5. `security.py` — 비밀번호 보안

- **Argon2** 알고리즘 사용 (`pwdlib` 라이브러리)
- `hash_password(password)` → 해시 문자열 반환
- `verify_password(password, hash)` → 일치 여부 반환

---

### 3-6. `account.py` — 계정 API 및 로그아웃 연동

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/signup` | POST | 회원가입 (중복 username → 409, 비밀번호 8~128자) |
| `/api/login` | POST | 로그인 & 세션 발급 (실패 시 401 및 상세 메시지 반환) |
| `/api/me` | GET | 현재 로그인 사용자 정보 반환 (`UserResponse`) |
| `/api/logout` | POST | 세션 초기화 (`204 No Content` 반환, 비로그인 상태도 204) |

- `Username` 타입: 소문자 변환, 영숫자·언더스코어만 허용, 3~30자
- `Password`: 최소 8자, 최대 128자 (`SecretStr`로 응답 및 로그에서 제외)
- **프론트엔드 로그아웃 연동 (`common.js` & `base.html`)**:
  - 네비게이션 로그아웃 버튼(`navLogoutBtn`) 클릭 시 `POST /api/logout` 비동기 요청.
  - **오직 HTTP 204 성공 시에만** 로그인 페이지(`/login`)로 이동.
  - 200/401/403/500 또는 네트워크 장애 시 페이지를 이동하지 않고 상단 `#logoutError` 배너에 안내문구를 표시(`display: flex`).
  - 요청 중 버튼 비활성화(`disabled = true`)로 중복 클릭을 차단하며, 실패 시 버튼을 다시 활성화하여 즉시 재시도 가능.

---

### 3-7. `account_db.py` — 사용자 DB CRUD

| 함수 | 설명 |
|------|------|
| `create_user(db, username, password_hash)` | 사용자 저장, ID 반환 |
| `get_user_by_username(db, username)` | 사용자명으로 조회 |
| `get_user_by_id(db, user_id)` | ID로 조회 |

---

### 3-8. `llm.py` — AI 채팅 API

**`POST /api/chat`** 처리 흐름:

```text
1. 로그인 인증 (get_current_user)
2. CSRF 헤더 검사 (require_csrf_header)
3. 최근 5쌍 대화 문맥 조회 (get_recent_chats_by_user)
4. user/assistant 형식으로 history 구성
5. AI 호출 (llm_connect.generate_answer)
   ├── APITimeoutError → AITimeoutError → HTTP 504 (Gateway Timeout)
   └── OpenAIError / JSONDecodeError / 비정상 응답 → AIServiceError → HTTP 502 (Bad Gateway)
6. 질문·답변 DB 저장 (create_chat)
7. {"answer": "..."} 반환 (DB 저장까지 성공해야 최종 반환)
```

- 질문 최대 길이: **1000자** (공백 문자열 차단)
- 동기 DB 작업은 `run_in_threadpool`로 비동기 이벤트 루프 차단 없이 실행
- AI 호출 실패 또는 비정상 응답 시 질문과 답변은 **DB에 저장되지 않음**

---

### 3-9. `llm_connect.py` — AI 서비스 통신 및 안전한 응답 검증

- `AsyncOpenAI` 클라이언트를 **모듈 수준에서 재사용** (커넥션 풀 효율 극대화)
- `max_retries=0`: 중복 질문 방지 및 명확한 실패 감지를 위해 SDK 자동 재시도 비활성화
- **예외 체계 및 응답 유효성 검증**:
  | 상황 | 원인 | 변환 예외 | HTTP 응답 |
  |------|------|-----------|-----------|
  | 시간 초과 | `APITimeoutError` | `AITimeoutError` | 504 |
  | SDK 통신 실패 | `OpenAIError` (인증/네트워크/5xx) | `AIServiceError` | 502 |
  | 응답 파싱 실패 | `JSONDecodeError` (손상된 JSON 본문) | `AIServiceError` | 502 |
  | 비정상 페이로드 | `choices` 누락/빈배열, `content`가 문자열 아님 | `AIServiceError` (`InvalidAnswer`) | 502 |
  | 빈 답변 | `content.strip()` 결과가 공백 | `AIServiceError` (`EmptyAnswer`) | 502 |
- **보안 및 민감정보 보호**:
  - `raise ... from None`으로 내부 예외 체인 차단.
  - 외부 제공자 API 키, 실패 원문, 질문/답변 본문은 클라이언트 에러 응답 및 로그에 **절대 노출하지 않음** (`ai_call_failure`에는 `model`, `elapsed`, `error_type`만 기록).

---

### 3-10. `history.py` — 대화 기록 API

**`GET /api/me/chats`**:
- 로그인 사용자의 모든 대화 기록을 **최신순**으로 반환
- 응답 필드: `id`, `question`, `answer`, `created_at` (UTC ISO 형식)

---

### 3-11. `chat_db.py` — 대화 기록 DB CRUD

| 함수 | 설명 |
|------|------|
| `create_chat(db, user_id, question, answer)` | 대화 한 쌍 저장, chat_id 반환 |
| `get_chats_by_user(db, user_id)` | 전체 기록 (최신순) |
| `get_recent_chats_by_user(db, user_id)` | 최근 5쌍 (오름차순, AI 문맥용) |

---

### 3-12. `pages.py` — HTML 페이지 라우터

| 경로 | 인증 상태 | 동작 |
|------|-----------|------|
| `GET /` | — | `/login`으로 리다이렉트 (307) |
| `GET /login` | 로그인 중 | `/chat`으로 리다이렉트 (303) |
| `GET /signup` | 로그인 중 | `/chat`으로 리다이렉트 (303) |
| `GET /chat` | 비로그인 | `/login`으로 리다이렉트 (303) |
| `GET /history` | 비로그인 | `/login`으로 리다이렉트 (303) |

---

### 3-13. 프론트엔드 핵심 동작 (`chat.js`, `history.js`, `login.js`)

- **한글 IME 조합 중 Enter 처리 (`chat.js`)**:
  - 한글 자모 조합 중 Enter를 누를 때 중복 전송되는 문제를 해결하기 위해 `compositionstart`, `compositionend` 이벤트로 `isComposing` 상태를 관리.
  - `keydown` 이벤트에서 `isComposing || e.isComposing || e.keyCode === 229`일 경우 제출을 차단.
  - 일반 Enter는 질문 전송, `Shift + Enter`는 입력창 줄바꿈 유지.
- **XSS 방지**:
  - 모든 사용자 질문과 AI 답변을 `element.textContent`로 삽입하여 악성 스크립트 실행 방지.
- **재시도 메커니즘**:
  - 502/504 오류 시 화면에 재시도 버튼을 띄우고, 마지막 실패 질문(`lastFailedQuestion`)을 복원하여 재전송 가능.

---

## 4. DB 테이블 구조

### `users` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `username` | String(30) UNIQUE | 소문자 정규화 사용자명 |
| `password_hash` | Text | Argon2 해시 (무작위 salt 포함) |
| `created_at` | DateTime | 생성 시각 (UTC) |

### `chats` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `user_id` | INTEGER FK(users.id) | 사용자 참조 (인덱스) |
| `question` | Text | 사용자 질문 (최대 1000자) |
| `answer` | Text | AI 답변 |
| `created_at` | DateTime | 생성 시각 (UTC) |

---

## 5. 요청 흐름 다이어그램

```
[브라우저]
   │
   ├─ GET /login, /signup, /chat, /history
   │       └─ pages.py (Jinja2 HTML 반환)
   │
   ├─ POST /api/signup
   │       └─ account.py → account_db.py → users 테이블 (중복 확인 및 저장)
   │
   ├─ POST /api/login
   │       └─ account.py → account_db.py → 세션 쿠키 발급 (askmate_session)
   │
   ├─ POST /api/chat
   │       └─ llm.py
   │              ├─ chat_db.py (최근 5쌍 문맥 조회)
   │              ├─ llm_connect.py (AI API 호출 및 응답 형식 검증)
   │              └─ chat_db.py (성공 시 질문·답변 한 쌍 DB 저장)
   │
   ├─ GET /api/me/chats
   │       └─ history.py → chat_db.py → chats 테이블 (최신순 전체 조회)
   │
   └─ POST /api/logout
           └─ account.py → 세션 초기화 → 204 No Content 반환
```

---

## 6. 보안 설계 요약

| 항목 | 구현 방식 |
|------|-----------|
| 비밀번호 보안 | Argon2 해시 (`pwdlib`), 무작위 salt, 최소 8자 |
| CSRF 방어 | POST 요청 시 `X-Requested-With: XMLHttpRequest` 커스텀 헤더 강제 검증 |
| 세션 보안 | 서버 서명 쿠키 (`SessionMiddleware`), `HttpOnly`, `SameSite=Lax` |
| 민감정보 보호 | API 키·원문 에러 클라이언트 미노출, `hide_parameters=True`로 SQL 바인딩 로그 보호 |
| XSS 방어 | `textContent` 기반 DOM 조작, Jinja2 자동 이스케이프 |
| 캐시 제어 | 민감한 인증 응답에 `Cache-Control: no-store` 헤더 적용 |

---

## 7. 주요 의존 라이브러리

| 라이브러리 | 용도 |
|-----------|------|
| `fastapi` | 비동기 웹 프레임워크 |
| `sqlalchemy` | ORM 및 SQLite DB 연결 |
| `starlette` | 미들웨어, 세션, 정적 파일 서빙 |
| `openai` | OpenAI 호환 AI API 비동기 클라이언트 (`AsyncOpenAI`) |
| `pwdlib` | Argon2 비밀번호 안전 해싱 |
| `python-dotenv` | `.env` 환경변수 로드 |
| `pydantic` | 요청 및 응답 데이터 스키마 유효성 검증 |
| `jinja2` | 서버 사이드 HTML 템플릿 렌더링 |

---

## 8. 테스트 및 품질 검증 (QA)

프로젝트는 회귀 결함을 방지하기 위해 백엔드와 프론트엔드 전반에 걸쳐 철저한 자동화 테스트를 갖추고 있습니다.

1. **백엔드 자동화 테스트 (`pytest`)**:
   - 실행: `uv run python -m pytest -q`
   - 결과: **148 passed** (회귀 검증 포함 전체 통과)
   - 주요 검증 항목:
     - `test_ai_chat.py`: AI 타임아웃(504), 게이트웨이 에러(502), 비정상 페이로드(malformed: null, 빈 배열, 문자열 아닌 content, 손상된 JSON) 시 502 변환 및 DB 미저장, 로그 마스킹, 정상 호출 복구 검증.
     - `test_config.py`: 세션 및 AI 설정 검증, `AI_TIMEOUT` 유한한 양수 검증 (`nan`, `inf`, `1e999`, `0.0` 차단, `0.5`, `30` 통과).
     - `test_auth.py`, `test_account.py`, `test_history.py` 등 인증/CRUD 전체 검증.

2. **프론트엔드 단위 테스트 (`node --test`)**:
   - 실행: `node --test tests/frontend/*.test.cjs` (추가 npm 패키지 의존성 없이 Node 22+ 내장 러너로 실행)
   - 결과: **12 passed**
   - 주요 검증 항목:
     - `chat-input.test.cjs`: 한글 조합(IME `isComposing`, `keyCode === 229`) 시 Enter 전송 방지, 일반 Enter 1회 전송, Shift+Enter 줄바꿈, 빈 공백 전송 차단 검증.
     - `logout.test.cjs`: 204 응답 시 로그인 페이지 이동, 200/401/403/500 및 네트워크 실패 시 에러 배너 노출 및 재시도 허용, 중복 요청 차단 검증.

---

*최초 작성: 2026-09-28 | 최종 갱신: 2026-10-01 (PR #36 반영 및 QA 결함 보완 검증 완료)*


