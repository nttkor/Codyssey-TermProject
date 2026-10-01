# AskMate 백엔드 공부 노트

**기준:** `fix/qa-findings` / `baa13d5` (PR #36 반영 완료). 코드 경로는 `backend/` 기준입니다. DB 세부 내용은 [database.md](database.md), 기능 호출 순서는 [flow.md](flow.md)에 있습니다.

## 1. 백엔드는 무엇을 책임지나요?

백엔드는 화면에서 받은 요청을 검증하고, 로그인한 사용자인지 판단하며, DB와 외부 AI를 연결합니다. 브라우저가 보내는 사용자 ID나 성공 표시를 그대로 믿지 않고 서버에서 판단해야 합니다.

| 계층 | 파일 | 책임 |
| --- | --- | --- |
| 앱 설정 | `app/main.py` | 미들웨어, 라우터, 시작·종료, 검증 오류 |
| 화면 라우트 | `app/pages.py` | HTML 렌더링과 로그인별 이동 |
| 계정 API | `app/account.py` | 가입·로그인·현재 사용자·로그아웃 |
| 공통 인증 | `app/auth.py` | 쿠키 세션의 사용자 확인, POST 헤더 검사 |
| 비밀번호 | `app/security.py` | Argon2 해시·검증 |
| 채팅 API | `app/llm.py` | 문맥 조회 → AI 호출 → 대화 저장 |
| AI 통신 | `app/llm_connect.py` | 제공자 요청·응답 확인·통신 예외 |
| 기록 API | `app/history.py` | 본인 기록을 응답 모델로 변환 |
| 설정·로그 | `app/config.py`, `config_validation.py`, `logger.py` | 환경 설정 검증과 관찰 |

## 2. Uvicorn·FastAPI·라우터

Uvicorn은 네트워크 요청을 받아 Python 앱으로 전달하는 ASGI 서버입니다. FastAPI는 URL을 함수에 연결하고 입력·응답 처리 등을 제공하는 웹 프레임워크입니다. 둘은 같은 역할이 아닙니다.

`uvicorn app.main:app`은 `app/main.py` 모듈 안의 `app` 객체를 실행하라는 뜻입니다. `main.py:47`의 `FastAPI(...)`가 그 객체입니다.

```python
app.include_router(account_router, prefix="/api")
```

라우터는 관련 API 함수의 묶음입니다. `account.py`의 `@router.post("/login")`과 `/api` 접두사가 합쳐져 `POST /api/login`이 됩니다. 같은 주소라도 HTTP 메서드가 다르면 다른 작업으로 구분할 수 있습니다.

확인 위치: `main.py:47~60`, `account.py:28,83`, `llm.py:35,44`, `history.py:27,37`입니다.

## 3. 시작·종료와 lifespan

`main.py:34~44`의 `lifespan()`은 앱 전체의 생명주기를 관리합니다.

- `yield` 이전: DB 준비와 시작 로그를 처리합니다.
- `yield` 구간: 앱이 요청을 받습니다.
- `finally`: 종료 시 `engine.dispose()`로 엔진 연결을 정리합니다.

`@asynccontextmanager`는 준비 → 사용 → 정리 구조를 만들기 위한 장치입니다. 요청마다 DB 전체를 초기화하는 것이 아닙니다. 요청별 DB 세션 생성은 별도로 `get_db()`가 담당합니다.

환경 설정은 앱 모듈을 가져오는 과정에서 검증됩니다. 설정이 잘못되면 요청을 기다렸다가 오류를 내는 대신 시작을 실패시키는 정책입니다. 구체적인 설정은 [operations.md](operations.md)에 있습니다.

## 4. HTTP 요청·응답·모델

### 4.1 Pydantic 요청 모델

Pydantic 모델은 “어떤 필드를 어떤 규칙으로 받을지” 정의합니다. 모델 인스턴스가 만들어졌다는 것은 기본 입력 형식 검사를 통과했다는 뜻입니다.

| 모델 | 위치 | 정책 |
| --- | --- | --- |
| `Username` 타입 별칭 | `account.py:31~40` | 공백 제거·소문자, 3~30자, 영문·숫자·밑줄 |
| `SignUpPayload` | `account.py:43~45` | 사용자명, 비밀번호 8~128자 |
| `LoginPayload` | `account.py:48~51` | 사용자명, 비밀번호 1~128자 |
| `ChatRequest` | `llm.py:38~41` | 공백 제거 후 질문 1~1,000자 |
| `UserResponse` | `account.py:54~56` | 공개 가능한 id·username만 응답 |
| `ChatResponse` | `history.py:30~34` | id·질문·답변·시각 응답 |

`Annotated[str, StringConstraints(...)]`는 문자열 타입에 검증 정보를 붙입니다. `SecretStr`는 객체를 출력할 때 비밀번호가 쉽게 드러나지 않도록 돕습니다. 암호화나 DB 해시를 대신하지 않으며, 실제 해시를 만들 때는 `get_secret_value()`로 원본을 꺼냅니다.

로그인 비밀번호의 최소 길이가 가입과 다른 이유는 현재 가입 정책으로 다시 가입시키는 것이 아니라 기존 해시와 일치하는지 확인하기 때문입니다. 비밀번호는 공백 제거·소문자 변환을 하지 않습니다.

### 4.2 검증 오류의 민감정보 제외

`main.validation_error():63~70`은 `RequestValidationError`를 422 응답으로 바꿉니다. 오류에서 `type`, `loc`, `msg`만 추출하여 원본 입력을 담을 수 있는 `input`, `ctx`를 제외합니다.

입력이 유효하지 않으면 비즈니스 함수가 실행되지 않습니다. 다만 인증·헤더 같은 의존성도 요청 처리 과정에 포함되므로 “모든 요청에서 본문 검증이 제일 먼저다”라고 외우면 안 됩니다. 현재 POST 라우트는 헤더 검사 의존성을 연결합니다.

### 4.3 응답 모델

`response_model=UserResponse`는 반환 형식을 제한하고 명세에도 반영합니다. DB 모델 전체를 반환하지 않고 공개 필드만 응답하도록 하는 설계입니다. `history.py`는 시간대 처리까지 수행하여 별도의 `ChatResponse` 목록을 만듭니다.

## 5. 의존성 주입: Depends

`Depends`는 함수가 필요한 준비 작업을 FastAPI에 맡기는 방식입니다. 모든 API마다 인증 코드와 DB 연결 코드를 복사하지 않게 합니다.

```text
llm.chat()에 필요한 것
  ├─ payload: ChatRequest → JSON 입력 검증
  ├─ user: Depends(get_current_user)
  │    └─ Depends(get_session_user)
  │         └─ Depends(get_db)
  └─ db: Depends(get_db)
```

위치는 `llm.py:44~49`, `auth.py:26~45`, `db_connect.py:52~55`입니다. FastAPI는 기본적으로 같은 요청 안의 같은 의존성 결과를 재사용합니다. 따라서 중첩 의존성에 `get_db`가 반복된다고 무조건 별도 세션을 매번 만든다고 생각하지 마세요. 서로 다른 요청은 독립적인 세션을 받습니다.

`dependencies=[Depends(require_csrf_header)]`는 결과 값을 함수 인자로 받지 않지만 검사를 수행해야 하는 경우입니다. 인증 사용자 객체는 함수에서 사용하므로 `user` 인자로 받습니다.

`get_db()`가 `yield`로 세션을 제공하면 FastAPI가 사용 후 정리까지 연결합니다. 여기서 `yield`는 반복용 데이터를 여러 번 보내려는 목적이 아니라 자원 수명을 관리하기 위한 패턴입니다.

## 6. 비밀번호 해시·salt·검증

위치: `security.py:5~15`, `account.signup():65~68`, `account.login():93~99`입니다.

해시는 비밀번호를 원본으로 쉽게 되돌릴 수 없는 검증용 결과로 바꾸는 방식입니다. 암호화처럼 복호화해서 원문을 찾는 설계가 아닙니다.

```text
가입: 원본 비밀번호 → Argon2 해시 → users.password_hash
로그인: 입력 비밀번호 + 저장 해시 → verify_password() → 참/거짓
```

salt는 같은 비밀번호도 서로 다른 해시가 되도록 섞는 무작위 값입니다. 라이브러리가 생성·관리하므로 직접 고정 salt를 코드에 넣지 않습니다. 해시 문자열에는 검증에 필요한 알고리즘·파라미터·salt 정보가 포함됩니다.

단순 문자열 SHA 해시보다 비밀번호 전용 알고리즘을 사용하는 이유는 대량의 추측 계산을 어렵게 만들기 위해서입니다. 하지만 해시로 DB에 저장해도 네트워크 전송은 별도 문제이므로 HTTPS가 필요합니다.

## 7. 쿠키와 로그인 세션

### 7.1 실제 구현

`main.py:48~55`는 `SessionMiddleware`를 설정합니다. `account.login():101~102`는 기존 세션을 비우고 `user_id`를 넣습니다. 세션 쿠키 이름은 `askmate_session`입니다.

```text
로그인 성공
  → request.session["user_id"] = DB 사용자 ID
  → 미들웨어가 서명된 쿠키 응답
  → 브라우저 저장
  → 이후 요청에 쿠키 전송
  → 미들웨어 검증
  → auth.get_session_user()가 DB 계정 확인
```

이 프로젝트에 서버 측 로그인 세션 테이블은 없습니다. 쿠키 데이터가 서명되어 전달되는 방식입니다. `request.session`은 요청 처리 중 사용할 수 있게 미들웨어가 제공하는 사전 형태의 데이터입니다.

### 7.2 서명과 암호화의 차이

- 서명: 비밀키 없이는 내용을 유효하게 바꾸기 어렵게 하며 변조를 검출합니다.
- 암호화: 비밀키 없이는 원래 내용을 읽기 어렵게 합니다.

서명된 쿠키 내용은 읽을 수 있으므로 비밀번호·해시·AI 키를 넣으면 안 됩니다. 현재는 사용자 ID만 넣습니다.

### 7.3 쿠키 보조 정책

프로젝트 설정·문서 기준으로 쿠키는 `HttpOnly`, `SameSite=Lax`, `Path=/`를 사용하며 HTTPS 전용 여부는 설정에 따릅니다.

- `HttpOnly`: 브라우저 JS의 직접 쿠키 접근을 제한합니다. 쿠키를 요청에 전송하는 것까지 막지는 않습니다.
- `SameSite=Lax`: 다른 사이트 맥락의 쿠키 전송을 제한하여 CSRF 위험을 줄입니다. 단독으로 모든 공격을 막는다는 뜻은 아닙니다.
- `Secure`에 해당하는 `https_only`: HTTPS에서만 전송하도록 합니다.
- `max_age`: 기본 3,600초의 유효기간 정책입니다.

세션 갱신의 세부 동작은 잠금된 Starlette 버전에 영향을 받습니다. `B7-1/docs/AUTH.md:86~96`은 현재 버전에서 조회만으로 유효기간이 연장되지 않는다고 설명합니다. 이 노트 작성 중 라이브러리 내부를 별도 확인하지는 않았습니다.

### 7.4 로그아웃의 한계

`account.logout():115~122`는 현재 요청 세션을 비웁니다. 정상 응답이면 현재 브라우저의 쿠키가 삭제되지만, 이미 복사된 유효 쿠키를 서버에서 개별 철회할 저장소는 없습니다. 다른 브라우저의 로그인도 유지될 수 있습니다.

개별 세션 즉시 철회가 필요하면 서버 측 세션 ID·만료 상태 등을 저장하는 설계가 필요합니다. 현재 없는 기능과 개선 방향을 구분해 주세요.

## 8. 인증·소유권·CSRF는 서로 다른 문제입니다

### 인증

“누구인가?”를 판단합니다. `auth.get_current_user():41~45`는 유효 계정이 없으면 401을 반환합니다.

### 소유권과 접근 제어

“그 사용자가 어떤 데이터를 볼 수 있는가?”를 판단합니다. `llm.chat()`과 `history.get_my_chats()`는 인증 결과의 `user.id`를 DB 필터에 전달합니다. 클라이언트가 임의의 `user_id`를 보내도 이를 소유자로 사용하지 않습니다.

### CSRF

CSRF는 다른 사이트가 사용자의 브라우저와 로그인 쿠키를 이용하여 원하지 않는 요청을 보내게 하는 문제입니다. 현재 `auth.require_csrf_header():15~23`는 커스텀 헤더 값을 확인하고, 다른 출처에 CORS를 허용하지 않는 구조를 전제로 사용합니다.

일반적인 다른 출처 웹 페이지가 커스텀 헤더 요청을 보내려면 브라우저의 사전 요청 검사를 거칩니다. 서버가 이를 허용하지 않는 전제에서 단순 폼 요청과 구분하는 전략입니다. 헤더 값은 비밀이 아니며 `curl`도 만들 수 있으므로 인증 토큰처럼 생각하면 안 됩니다.

프론트를 다른 출처로 분리하거나 광범위한 CORS를 허용하면 이 전제를 재검토해야 합니다. 헤더 검사는 로그인 검사나 XSS 방지와도 별개입니다.

## 9. AI 파이프라인

중심 함수는 `llm.chat():44~92`입니다.

1. 인증된 사용자 ID를 얻습니다.
2. DB에서 본인 최근 5쌍을 오래된 순서로 받습니다.
3. 각 쌍을 `role="user"`, `role="assistant"` 메시지로 펼칩니다.
4. `generate_answer()`를 기다립니다.
5. 성공한 답변과 질문을 저장합니다.
6. 저장까지 성공해야 `{answer}`를 반환합니다.

### 9.1 왜 과거 대화를 다시 보내나요?

현재 API 호출 자체가 이전 요청의 내용을 자동으로 기억한다고 가정하지 않습니다. 서버가 DB 기록을 읽어 메시지 목록에 포함해야 모델이 참고할 수 있습니다. “기억”은 모델 내부에 사용자별 기록을 영구 저장했다는 뜻이 아니라 이번 요청 입력에 과거 내용을 넣었다는 뜻입니다.

최근 5쌍은 간단한 개수 기반 정책입니다. 한 쌍의 답변이 매우 길면 토큰 사용량은 커질 수 있습니다. 현재 코드에는 토큰 예산, 과거 내용 요약, 대화방 분리, 시스템 메시지 정책이 없습니다.

### 9.2 OpenAI 호환 요청

`llm_connect.py:38~43`에서 `AsyncOpenAI`를 만들고 `base_url`, `api_key`, `timeout`, `max_retries=0`을 설정합니다. 게이트웨이가 OpenAI 형식의 API를 제공한다는 뜻이지, 반드시 특정 모델 하나만 사용한다는 뜻은 아닙니다. 모델은 환경 변수 `AI_MODEL`로 정합니다.

`_build_messages():46~49`는 원본 목록을 바꾸지 않고 새 목록 끝에 현재 질문을 한 번 추가합니다. `generate_answer():67~70`에서 SDK가 Chat Completions 요청과 인증 헤더를 처리합니다. AI 키는 브라우저로 보내지 않습니다.

### 9.3 응답이 200이어도 확인해야 합니다

`llm_connect.py:90~103`은 다음을 검사합니다.

- `choices`가 비어 있지 않은 목록인지 확인합니다.
- 첫 항목의 `message`와 `content`를 확인합니다.
- `content`가 문자열인지 확인합니다.
- 공백 제거 후 비어 있지 않은지 확인합니다.

정상 HTTP 상태와 정상 서비스 데이터는 다릅니다. 데이터 형식이 잘못되면 `AIServiceError`로 바꾸어 저장을 막습니다.

## 10. async/await와 스레드 풀

`llm.chat()`과 `generate_answer()`는 `async def`입니다. 외부 AI 응답을 기다리는 시간에 이벤트 루프가 다른 작업을 진행할 수 있도록 `await`를 사용합니다.

```text
외부 AI 네트워크 대기 → AsyncOpenAI + await
동기 SQLAlchemy 작업 → run_in_threadpool() + await
```

동기 DB 함수는 호출한 스레드에서 결과가 나올 때까지 실행합니다. 이를 비동기 함수 안에서 그대로 실행하면 이벤트 루프를 막을 수 있으므로 `llm.py:54,87`에서 스레드 풀에 넘깁니다.

`await`를 붙였다는 사실만으로 CPU 계산이 빨라지거나 DB가 비동기 드라이버로 바뀌는 것은 아닙니다. `account.py`, `history.py`, `pages.py`의 일반 `def` 라우트는 FastAPI가 동기 함수로 처리합니다.

같은 DB 세션을 여러 스레드가 동시에 안전하게 쓸 수 있다는 의미도 아닙니다. 현재 채팅의 DB 작업은 순서대로 기다립니다. 요청별 세션, 동시 사용 금지, SQLite의 쓰기 제약은 [database.md](database.md)를 참고해 주세요.

## 11. 예외를 사용자 응답으로 바꾸기

| 코드 | 어디서 만드는지 | 의미 |
| --- | --- | --- |
| 401 | `auth.get_current_user()`, `account.login()` | 비로그인 또는 자격 증명 불일치 |
| 403 | `auth.require_csrf_header()` | POST 헤더 조건 불충족 |
| 409 | `account.signup()` | 사용자명 고유 제약 충돌 |
| 422 | `main.validation_error()` | 요청 검증 오류 |
| 500 | 계정·문맥·기록·저장 예외 분기 | DB 등의 내부 실패 |
| 502 | `llm.chat()`의 `AIServiceError` 처리 | AI 호출·응답 문제 |
| 504 | `llm.chat()`의 `AITimeoutError` 처리 | AI 응답 대기 시간 초과 |

통신 예외를 서비스 예외로 바꾸는 곳은 `llm_connect.py:71~86`이고, 서비스 예외를 HTTP로 바꾸는 곳은 `llm.py:71~82`입니다. 이렇게 구분하면 AI 통신 함수가 웹 응답 정책을 직접 알 필요가 없습니다.

`raise ... from None`은 사용자용 예외를 만들면서 이전 예외 연결 표시를 억제하는 데 쓰입니다. 민감한 제공자 원문을 응답에 넣지 않는 설계와 함께 읽어 주세요. 원인 종류·시간은 별도 로그로 남깁니다.

현재 예상 밖의 모든 예외를 일괄 변환하지는 않습니다. SDK가 정의한 오류·JSON 오류·응답 검사·DB 오류에 대한 명시적인 분기라는 점을 기억해 주세요.

## 12. 저장과 반환의 순서

과제 목표의 문구가 “응답 반환 → 대화 로그 저장” 순서로 소개되어도, 현재 실제 코드는 **AI 응답 생성 → DB 저장 → 웹 응답 반환**입니다(`llm.py:84~92`). 공부할 때 설명 문구보다 실제 실행 순서를 기준으로 해야 합니다.

이 정책은 성공한 웹 응답이 저장 성공과 연결된다는 장점이 있습니다. 반대로 DB 저장이 실패하면 이미 만든 답변도 사용자에게 정상 반환하지 않습니다. AI 호출과 DB 저장을 하나의 DB 트랜잭션으로 완전히 되돌릴 수는 없습니다.

## 13. 설명 연습과 참고 개념

- Uvicorn과 FastAPI는 각각 어떤 역할을 하나요?
- `Depends(get_current_user)`가 없으면 어떤 문제가 생기나요?
- `SecretStr`, Argon2 해시, 쿠키 서명, HTTPS는 어떻게 다른가요?
- 인증된 사용자 ID를 쓰는 것이 클라이언트 ID를 쓰는 것보다 안전한 이유는 무엇인가요?
- `async def` 안의 동기 DB 작업을 스레드 풀로 넘기는 이유는 무엇인가요?
- AI 통신 모듈과 HTTP 오류 변환을 나눈 이유는 무엇인가요?

추가 학습 링크:

- [FastAPI 의존성](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI 비동기 설명](https://fastapi.tiangolo.com/async/)
- [FastAPI 요청 본문](https://fastapi.tiangolo.com/tutorial/body/)
- [Starlette SessionMiddleware](https://www.starlette.io/middleware/#sessionmiddleware)
- [OWASP CSRF 예방](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
