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
│   │   ├── config.py           ← 환경변수 로드 및 검증
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
│   │   │   └── js/             ← chat.js, history.js, login.js 등
│   │   └── templates/          ← login.html, signup.html, chat.html 등
│   ├── data/                   ← SQLite DB 파일 저장 위치
│   ├── scripts/                ← 유틸리티 스크립트
│   └── tests/                  ← 테스트 코드
└── docs/                       ← 문서 폴더
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

### 3-2. `config.py` — 환경변수 설정

`.env` 파일(또는 배포 환경변수)을 읽어 전역 설정을 제공합니다.  
배포 환경변수가 `.env`보다 **우선** 적용됩니다.

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `DATABASE_PATH` | SQLite DB 파일 경로 | `data/askmate.db` |
| `SESSION_SECRET_KEY` | 세션 암호화 키 (필수) | — |
| `SESSION_MAX_AGE` | 세션 유지 시간(초) | `3600` |
| `SESSION_HTTPS_ONLY` | HTTPS 전용 쿠키 여부 | `false` |
| `AI_API_KEY` | AI 서비스 API 키 (필수) | — |
| `AI_BASE_URL` | AI 서비스 Base URL (필수) | — |
| `AI_MODEL` | 사용할 AI 모델명 (필수) | — |
| `AI_TIMEOUT` | AI 요청 제한 시간(초) | `30` |

> 필수 값이 비어 있거나 형식이 잘못되면 서버 **기동 시점에 RuntimeError**가 발생합니다.

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

### 3-6. `account.py` — 계정 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/signup` | POST | 회원가입 (중복 username → 409) |
| `/api/login` | POST | 로그인 & 세션 발급 |
| `/api/me` | GET | 현재 로그인 사용자 정보 반환 |
| `/api/logout` | POST | 세션 초기화 (비로그인 상태도 성공) |

- `Username` 타입: 소문자 변환, 영숫자·언더스코어만 허용, 3~30자
- `Password`: 최소 8자, 최대 128자 (`SecretStr`로 응답에서 제외)

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

```
1. 로그인 인증 (get_current_user)
2. CSRF 헤더 검사 (require_csrf_header)
3. 최근 5쌍 대화 문맥 조회 (get_recent_chats_by_user)
4. user/assistant 형식으로 history 구성
5. AI 호출 (llm_connect.generate_answer)
   ├── 타임아웃 → AITimeoutError → HTTP 504
   └── 기타 실패 → AIServiceError → HTTP 502
6. 질문·답변 DB 저장 (create_chat)
7. {"answer": "..."} 반환
```

- 질문 최대 길이: **1000자**
- 동기 DB 작업은 `run_in_threadpool`로 비동기 환경에서 실행

---

### 3-9. `llm_connect.py` — AI 서비스 통신

- `AsyncOpenAI` 클라이언트를 **모듈 수준에서 재사용** (커넥션 풀 효율)
- `max_retries=0`: 중복 질문 방지를 위해 자동 재시도 비활성화
- **예외 체계**:
  | 예외 | 원인 | HTTP 응답 |
  |------|------|-----------|
  | `AITimeoutError` | `APITimeoutError` (제한 시간 초과) | 504 |
  | `AIServiceError` | `OpenAIError` (연결·인증·제공자 오류) 또는 빈 응답 | 502 |
- AI 키, 오류 상세, 입력 내용은 사용자 응답에 **절대 노출하지 않음**

---

### 3-10. `history.py` — 대화 기록 API

**`GET /api/me/chats`**:
- 로그인 사용자의 모든 대화 기록을 **최신순**으로 반환
- 응답 필드: `id`, `question`, `answer`, `created_at` (UTC)

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
| `GET /` | — | `/login`으로 리다이렉트 |
| `GET /login` | 로그인 중 | `/chat`으로 리다이렉트 |
| `GET /signup` | 로그인 중 | `/chat`으로 리다이렉트 |
| `GET /chat` | 비로그인 | `/login`으로 리다이렉트 |
| `GET /history` | 비로그인 | `/login`으로 리다이렉트 |

---

## 4. DB 테이블 구조

### `users` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `username` | String(30) UNIQUE | 소문자 사용자명 |
| `password_hash` | Text | Argon2 해시 |
| `created_at` | DateTime | 생성 시각 (UTC) |

### `chats` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `user_id` | INTEGER FK(users.id) | 사용자 참조 (인덱스) |
| `question` | Text | 사용자 질문 |
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
   │       └─ account.py → account_db.py → users 테이블
   │
   ├─ POST /api/login
   │       └─ account.py → account_db.py → 세션 발급
   │
   ├─ POST /api/chat
   │       └─ llm.py
   │              ├─ chat_db.py (최근 5쌍 조회)
   │              ├─ llm_connect.py (AI API 호출)
   │              └─ chat_db.py (질문·답변 저장)
   │
   └─ GET /api/me/chats
           └─ history.py → chat_db.py → chats 테이블
```

---

## 6. 보안 설계 요약

| 항목 | 구현 방식 |
|------|-----------|
| 비밀번호 | Argon2 해시 (무작위 salt) |
| CSRF 방어 | `X-Requested-With: XMLHttpRequest` 헤더 강제 |
| 세션 | 서버 측 암호화 쿠키 (`SESSION_SECRET_KEY`) |
| AI 오류 | 제공자 오류 상세·API 키 사용자 응답에 미노출 |
| DB 로그 | `hide_parameters=True`로 SQL 인자(해시 등) 로그 제외 |
| 캐시 제어 | 민감 응답에 `Cache-Control: no-store` 헤더 추가 |

---

## 7. 주요 의존 라이브러리

| 라이브러리 | 용도 |
|-----------|------|
| `fastapi` | 웹 프레임워크 |
| `sqlalchemy` | ORM / DB 연결 |
| `starlette` | 미들웨어, 세션, 정적 파일 |
| `openai` | AI API 클라이언트 (AsyncOpenAI) |
| `pwdlib` | Argon2 비밀번호 해시 |
| `python-dotenv` | `.env` 파일 로드 |
| `pydantic` | 요청/응답 데이터 검증 |
| `jinja2` | HTML 템플릿 렌더링 |

---

*최초 작성: 2026-09-28 | 브랜치: nttkor*


