# 테스트·시연 가이드

AskMate를 **내 컴퓨터에서 켜고, 잘 동작하는지 확인하고, 발표에서 시연하는 방법**을 정리한 문서입니다.

백엔드를 직접 만들지 않는 팀원도 따라 할 수 있도록 명령어를 그대로 복사해 쓸 수 있게 적었습니다.
막히면 맨 아래 [자주 겪는 문제](#자주-겪는-문제)를 먼저 보세요.

- 설치와 실행의 기본 설명: [README](../README.md)
- API 요청·응답 규격: [API 명세](API.md)
- 화면 작업 안내: [프론트엔드 안내](FRONTEND.md)

---

## 0. 미리 알아둘 것

### 이 프로젝트는 어떻게 나뉘어 있나

```
브라우저 화면  →  FastAPI 서버  →  DB(SQLite) 에 대화 저장
  (HTML/CSS/JS)                 →  AI 게이트웨이에 질문 전달
```

화면은 서버에 **HTTP 요청**을 보내고, 서버는 **JSON**으로 답합니다.
그래서 확인할 곳이 두 군데입니다.

| 확인 대상 | 방법 |
| --- | --- |
| 서버가 제대로 답하는가 | 아래 [4. API 직접 확인](#4-api-직접-확인)의 `curl` 명령 |
| 화면이 제대로 보이는가 | 브라우저로 접속해서 눈으로 확인 |

### 용어 세 개만

- **서버를 켠다**: 터미널에서 명령을 실행하면 컴퓨터가 웹사이트 역할을 시작합니다. 터미널을 닫으면 꺼집니다.
- **포트**: 서버의 문 번호입니다. 이 프로젝트는 `8000`번을 씁니다. 주소는 `http://127.0.0.1:8000`입니다.
- **`127.0.0.1`**: 내 컴퓨터를 가리키는 주소입니다. 다른 사람은 이 주소로 접속할 수 없습니다.

---

## 1. 최초 1회 준비

이 단계는 **처음 한 번만** 하면 됩니다.

### 1-1. 저장소 받기

```bash
git clone https://github.com/seven2762/Codyssey-TermProject.git
cd Codyssey-TermProject
```

이미 받아두었다면 최신 코드로 맞춥니다.

```bash
git switch develop
git pull
```

### 1-2. 패키지 설치

```bash
cd backend
uv sync
```

`uv`가 없다면 [uv 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)를 먼저 따르세요.
Python 3.14가 없어도 `uv`가 알아서 내려받습니다.

### 1-3. `.env` 파일 만들기

서버는 비밀 값을 `backend/.env` 파일에서 읽습니다. **이 파일은 Git에 올라가지 않습니다.**
없으면 서버가 아예 켜지지 않으니 꼭 만들어야 합니다.

```bash
# backend 폴더 안에서 실행합니다
cp .env.example .env
```

그다음 세션 서명키를 하나 만듭니다.

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

출력된 긴 문자열을 복사해서 `backend/.env`를 열고 **두 줄만** 채웁니다.

```
SESSION_SECRET_KEY=여기에_방금_복사한_값
AI_API_KEY=팀에서_전달받은_키
```

- `SESSION_SECRET_KEY`는 로그인 상태를 서명하는 값입니다. 팀원끼리 같을 필요가 없으니 각자 만들면 됩니다.
- `AI_API_KEY`는 학교에서 받은 키입니다. **팀에 물어보고 개인적으로 전달받으세요.**
  카카오톡·DM 등으로 받고, 절대 코드나 커밋에 넣지 마세요.
- 나머지(`AI_BASE_URL`, `AI_MODEL` 등)는 이미 값이 들어 있으니 건드리지 않습니다.

---

## 2. 서버 켜고 끄기

### 켜기

```bash
cd backend
uv run uvicorn app.main:app --reload
```

아래처럼 나오면 성공입니다.

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

`--reload`는 코드를 수정하면 서버가 자동으로 다시 시작하는 옵션입니다. 개발할 때 편합니다.

### 끄기

서버를 켠 터미널에서 **`Ctrl` + `C`** 를 누릅니다.

### 잘 켜졌는지 1초 만에 확인

브라우저에서 <http://127.0.0.1:8000/health> 를 엽니다.

```json
{"status": "ok"}
```

이 화면이 나오면 서버는 정상입니다.

> 서버가 안 켜지고 빨간 글씨가 나온다면 [자주 겪는 문제](#자주-겪는-문제)로 가세요.

---

## 3. 자동 테스트 돌리기

사람이 일일이 눌러보지 않아도, 미리 만들어 둔 검사를 한 번에 실행할 수 있습니다.
**코드를 고친 뒤에는 이걸 먼저 돌려보세요.**

서버를 켠 터미널 말고 **새 터미널**을 열어서 실행합니다.

```bash
cd backend
uv run python -m pytest -q
```

### 결과 읽는 법

```
122 passed, 1 warning in 10.00s
```

- `passed` = 통과한 검사 개수입니다. 위 숫자는 예시이며, 테스트 추가에 따라 달라질 수 있지만 **`failed`가 0이면 정상**입니다.
- `warning`은 오류가 아닙니다. 무시해도 됩니다.

실패하면 이렇게 나옵니다.

```
FAILED tests/test_login.py::test_login_success - assert 403 == 200
1 failed, 121 passed
```

`FAILED` 옆의 파일 이름과 마지막 줄(`assert 403 == 200`)을 팀에 그대로 알려주면 됩니다.
`403`이 실제 결과, `200`이 기대한 결과라는 뜻입니다.

### 특정 파일만 돌리기

```bash
uv run python -m pytest -q tests/test_login.py
```

---

## 4. API 직접 확인

화면을 만들기 전에 **서버가 무엇을 돌려주는지** 알아야 합니다.
아래 명령을 순서대로 실행하면 회원가입 → 로그인 → 질문 → 기록 조회를 전부 확인할 수 있습니다.

서버를 켜 둔 상태에서, **새 터미널**에서 실행하세요.

### 준비: 반복해서 쓸 값 정하기

```bash
BASE=http://127.0.0.1:8000
COOKIE=/tmp/askmate_cookie.txt
```

`COOKIE`는 로그인 상태를 저장해 두는 파일입니다. 브라우저가 자동으로 하는 일을 터미널에서 흉내 내는 것입니다.

### 4-1. 회원가입

```bash
curl -i -X POST $BASE/api/signup \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"username":"testuser","password":"my long test password"}'
```

성공하면 `HTTP/1.1 201 Created`와 함께 아래가 나옵니다.

```json
{"id":1,"username":"testuser"}
```

> **`X-Requested-With: XMLHttpRequest` 헤더는 모든 POST 요청에 반드시 넣어야 합니다.**
> 빠뜨리면 `403`이 납니다. 자세한 이유는 [인증 안내](AUTH.md)에 있습니다.
> 화면의 JavaScript에서 `fetch`를 쓸 때도 똑같이 넣어야 합니다.

### 4-2. 로그인

```bash
curl -i -c $COOKIE -X POST $BASE/api/login \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"username":"testuser","password":"my long test password"}'
```

`-c $COOKIE`는 받은 로그인 쿠키를 파일에 저장하라는 뜻입니다.
`200 OK`와 `{"id":1,"username":"testuser"}`가 나오면 성공입니다.

### 4-3. 내가 누구인지 확인

```bash
curl -i -b $COOKIE $BASE/api/me
```

`-b $COOKIE`는 저장해 둔 로그인 쿠키를 함께 보내라는 뜻입니다.
`{"id":1,"username":"testuser"}`가 나옵니다.

쿠키 없이 보내면 `401`이 납니다. 직접 해보세요.

```bash
curl -i $BASE/api/me
```

### 4-4. AI에게 질문하기

```bash
curl -i -b $COOKIE -X POST $BASE/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"question":"파이썬이 뭔지 한 문장으로 알려줘"}'
```

1초쯤 기다리면 답이 옵니다.

```json
{"answer":"파이썬은 문법이 간단해서 배우기 쉬운 프로그래밍 언어입니다."}
```

### 4-5. 이어서 질문하기 (문맥 확인)

```bash
curl -i -b $COOKIE -X POST $BASE/api/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"question":"방금 뭐라고 했는지 요약해줘"}'
```

앞의 질문을 기억한 답이 나오면 **최근 대화 문맥 기능이 동작하는 것**입니다.
서버가 최근 5쌍의 질문·답변을 자동으로 함께 보내 줍니다. 화면에서 따로 보낼 필요가 없습니다.

### 4-6. 내 대화 기록 조회

```bash
curl -b $COOKIE $BASE/api/me/chats
```

최신순으로 배열이 나옵니다.

```json
[{"id":2,"question":"방금 뭐라고...","answer":"...","created_at":"2026-09-22T05:10:00.000000Z"},
 {"id":1,"question":"파이썬이 뭔지...","answer":"...","created_at":"2026-09-22T05:09:55.000000Z"}]
```

### 4-7. 로그아웃

```bash
curl -i -b $COOKIE -c $COOKIE -X POST $BASE/api/logout \
  -H 'X-Requested-With: XMLHttpRequest'
```

`204 No Content`가 나옵니다. **본문이 비어 있는 것이 정상입니다.**
화면에서 이 응답을 JSON으로 읽으려 하면 오류가 나니 주의하세요.

---

## 5. 브라우저로 화면 확인

서버를 켠 상태에서 아래 주소를 엽니다.

| 주소 | 설명 |
| --- | --- |
| <http://127.0.0.1:8000/login> | 로그인 화면 |
| <http://127.0.0.1:8000/signup> | 회원가입 화면 |
| <http://127.0.0.1:8000/chat> | 채팅 화면 (로그인 필요) |
| <http://127.0.0.1:8000/history> | 대화 기록 화면 (로그인 필요) |
| <http://127.0.0.1:8000/docs> | **API를 브라우저에서 눌러볼 수 있는 자동 문서** |

### 로그인하지 않으면 못 들어갑니다

`/chat`과 `/history`는 로그인하지 않은 상태로 열면 **자동으로 `/login`으로 이동**합니다.
이건 버그가 아니라 의도된 접근 제어입니다.

### `/docs`를 활용하세요

`/docs`에 들어가면 API 목록이 나오고, `Try it out` 버튼으로 직접 요청을 보내볼 수 있습니다.
`curl`이 어렵게 느껴지면 여기서 먼저 익히는 편이 빠릅니다.

### 브라우저 개발자 도구 보는 법

화면이 이상하게 동작할 때 원인을 찾는 가장 빠른 방법입니다.

1. 브라우저에서 **`F12`** (맥은 `Cmd + Option + I`)를 누릅니다.
2. **Console** 탭: JavaScript 오류가 빨간 글씨로 나옵니다.
3. **Network** 탭: 화면이 서버에 보낸 요청이 전부 보입니다.
   - 요청을 클릭하면 **Status**(응답 코드), **Headers**(보낸 헤더), **Response**(서버 답)를 볼 수 있습니다.
   - 빨간색으로 표시된 요청이 실패한 것입니다.

---

## 6. 오류 코드 읽는 법

서버는 숫자로 결과를 알려줍니다. **숫자만 봐도 어디가 문제인지 알 수 있습니다.**

| 코드 | 뜻 | 보통 원인 | 화면에서 할 일 |
| --- | --- | --- | --- |
| `200` | 성공 | | 결과를 표시 |
| `201` | 새로 만들어짐 | 회원가입 성공 | 로그인 화면으로 안내 |
| `204` | 성공했지만 내용 없음 | 로그아웃 성공 | **JSON 파싱 금지**, 비로그인 화면으로 |
| `401` | 로그인 안 됨 | 쿠키 없음, 세션 만료(1시간) | 로그인 화면으로 이동 |
| `403` | 헤더 없음 | **`X-Requested-With` 빠뜨림** | 요청 코드를 고쳐야 함 |
| `409` | 이미 있음 | 중복된 사용자명 | "이미 사용 중입니다" 표시 |
| `422` | 입력값이 규칙에 안 맞음 | 아래 [입력 규칙](#입력-규칙) 참고 | 입력창 옆에 안내 |
| `500` | 서버 내부 문제 | DB 저장·조회 실패 | `detail` 문구를 그대로 표시 |
| `502` | AI 연결 실패 | 게이트웨이 오류, 키 문제 | "다시 시도" 버튼 표시 |
| `504` | AI 응답 지연 | 30초 안에 답이 안 옴 | "다시 시도" 버튼 표시 |

`502`와 `504`일 때 `detail` 문구는 **그대로 화면에 보여도 안전합니다.** API 키 같은 민감한 정보가 들어 있지 않습니다.

### 입력 규칙

`422`가 나면 아래 규칙 중 하나를 어긴 것입니다.

| 항목 | 규칙 |
| --- | --- |
| 사용자명 | 3~30자, 영문·숫자·밑줄(`_`)만. 앞뒤 공백은 제거되고 **소문자로 저장**됩니다 |
| 비밀번호(가입) | 8~128자 |
| 질문 | 앞뒤 공백 제거 후 1~1,000자 |

`422` 응답의 `detail`은 **문자열이 아니라 배열**입니다. 다른 오류와 처리 방법이 다릅니다.

```json
{"detail":[{"type":"too_short","loc":["body","password"],"msg":"..."}]}
```

---

## 7. 시연하는 방법

발표에서 보여줄 순서입니다. **미리 한 번 연습해 보세요.**

### 시연 전 점검표

발표 직전에 아래를 확인합니다.

- [ ] `backend/.env`에 `SESSION_SECRET_KEY`와 `AI_API_KEY`가 채워져 있다
- [ ] `uv run python -m pytest -q`가 전부 통과한다
- [ ] 서버가 켜지고 `/health`가 `{"status":"ok"}`를 준다
- [ ] 인터넷이 연결되어 있다 (AI 호출에 필요합니다)
- [ ] AI 질문을 한 번 미리 보내서 답이 오는지 확인했다
- [ ] 시연용 계정을 미리 만들어 두었다

### 깨끗한 상태에서 시작하기

이전 테스트 기록이 화면에 남아 있으면 지저분해 보입니다.
**DB를 지우면 계정과 대화가 전부 사라지고 처음 상태로 돌아갑니다.**

```bash
cd backend
rm -f data/askmate.db
```

서버를 다시 켜면 빈 DB가 자동으로 만들어집니다.

> 시연 직전에만 하세요. 팀원과 공유하는 서버에서는 하지 마세요.

### 시연 순서

| 순서 | 보여줄 것 | 말할 내용 |
| --- | --- | --- |
| 1 | `/signup`에서 회원가입 | "비밀번호는 Argon2로 해시해서 저장합니다" |
| 2 | `/login`에서 로그인 | "세션 쿠키를 발급하고 1시간 동안 유지됩니다" |
| 3 | `/chat`에서 질문 1개 | "서버가 AI에 요청하고 답변을 DB에 저장합니다" |
| 4 | **이어서 질문** ("방금 뭐라고 했지?") | "최근 5쌍의 대화를 문맥으로 함께 보냅니다" |
| 5 | `/history`에서 기록 확인 | "본인 기록만 최신순으로 조회됩니다" |
| 6 | 로그아웃 후 `/chat` 접속 시도 | "로그인하지 않으면 접근이 차단됩니다" |

### 보여주면 좋은 것

**다른 사람 기록이 안 보인다는 점**은 강조할 만합니다.
계정 두 개를 미리 만들어 두고, B 계정으로 로그인했을 때 A의 대화가 안 보이는 것을 보여주면 됩니다.

**오류 처리**도 보여줄 수 있습니다. 빈 질문을 전송하거나 1,000자를 넘겨 보면 안내 문구가 뜹니다.

**서버 로그**를 띄워 두면 요청이 처리되는 과정이 실시간으로 보입니다.

```bash
tail -f backend/app.log
```

```
request_received user_id=1 path=/api/chat
ai_call_started model=gpt-5.4-mini message_count=3 timeout=30.0
ai_call_success model=gpt-5.4-mini elapsed=0.896 answer_length=36
db_save_success operation=chat user_id=1 chat_id=2
```

질문·답변 내용과 API 키는 **일부러 로그에 남기지 않습니다.** 이것도 설명할 거리입니다.

### 배포된 서버에서 시연하기

`develop`에 머지되면 OCI 서버에 자동 배포됩니다. 아래 주소로 **누구나 접속할 수 있습니다.**

## http://134.185.97.62

발표할 때는 이 주소를 그대로 쓰면 됩니다. 내 컴퓨터에서 서버를 켜지 않아도 됩니다.
평가자나 청중도 각자 기기에서 같은 주소로 들어와 직접 써 볼 수 있습니다.

접속되지 않으면 아래를 확인하세요.

```bash
curl --fail http://134.185.97.62/health
```

`{"status":"ok"}`가 나오면 서버는 정상입니다.
응답이 없으면 배포가 실패했을 수 있으니 GitHub Actions의 최근 실행 결과를 확인하세요.
배포 구조와 서버 설정은 [배포 안내](DEPLOYMENT.md)에 정리되어 있습니다.

> **주의**: 배포 서버는 HTTP로 공개되어 있어 비밀번호가 암호화되지 않은 채 전송됩니다.
> 시연용 계정만 쓰고, 평소 쓰는 비밀번호를 넣지 마세요.

발표장 네트워크가 불안할 수 있으니 **내 컴퓨터에서 켜는 방법도 함께 준비해 두는 편이 안전합니다.**

### 로컬과 배포 서버의 차이

| | 로컬 | 배포 서버 |
| --- | --- | --- |
| 주소 | `http://127.0.0.1:8000` | `http://134.185.97.62` |
| 접속 범위 | 내 컴퓨터만 | 누구나 |
| DB | `backend/data/askmate.db` | 서버의 Docker 볼륨 |
| 코드 | 지금 내 폴더의 코드 | `develop`에 머지된 코드 |

**배포 서버의 DB는 지우지 마세요.** 다른 팀원의 시연 계정이 들어 있을 수 있습니다.

---

## 자주 겪는 문제

### `RuntimeError: SESSION_SECRET_KEY를 .env 또는 실행 환경에 설정하세요.`

`backend/.env`가 없거나 `SESSION_SECRET_KEY`가 비어 있습니다.
[1-3. `.env` 파일 만들기](#1-3-env-파일-만들기)를 다시 하세요.

### `RuntimeError: AI_API_KEY를 .env 또는 실행 환경에 설정하세요.`

`backend/.env`의 `AI_API_KEY`가 비어 있습니다. 팀에서 키를 받아 채워 넣으세요.

### 모든 요청이 `403`으로 실패합니다

POST 요청에 `X-Requested-With: XMLHttpRequest` 헤더가 빠졌습니다.
`fetch`를 쓴다면 이렇게 넣어야 합니다.

```javascript
fetch('/api/login', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',   // 이 줄이 없으면 403
    },
    body: JSON.stringify({ username, password }),
});
```

`GET` 요청(`/api/me`, `/api/me/chats`)에는 필요 없습니다.

### `Address already in use` / 포트가 이미 사용 중

서버가 이미 켜져 있습니다. 이전 터미널에서 `Ctrl + C`로 끄거나, 다른 포트를 쓰세요.

```bash
uv run uvicorn app.main:app --reload --port 8001
```

### 채팅만 `502`가 납니다

AI 게이트웨이에 연결하지 못한 것입니다. 순서대로 확인하세요.

1. 인터넷이 연결되어 있는가
2. `backend/.env`의 `AI_API_KEY`가 올바른가
3. 아래 명령으로 게이트웨이가 살아 있는지 확인

```bash
curl -H "Authorization: Bearer 여기에_키" https://copa.codyssey.kr/v1/models
```

모델 목록이 나오면 게이트웨이는 정상이고, 키나 설정 문제입니다.

### 로그인했는데 자꾸 로그아웃됩니다

세션 유효기간이 기본 1시간입니다. 다시 로그인하면 됩니다.
`backend/.env`의 `SESSION_SECRET_KEY`를 바꾸면 기존 로그인이 전부 무효가 되니 주의하세요.

### 화면을 고쳤는데 반영이 안 됩니다

브라우저가 이전 CSS·JavaScript를 기억하고 있어서입니다. **강력 새로고침**을 하세요.

- 윈도우: `Ctrl + Shift + R`
- 맥: `Cmd + Shift + R`

### 테스트가 갑자기 많이 실패합니다

먼저 최신 코드를 받고 패키지를 다시 맞춰 보세요.

```bash
git switch develop && git pull
cd backend && uv sync
uv run python -m pytest -q
```

그래도 실패하면 실패한 테스트 이름과 마지막 몇 줄을 그대로 팀에 공유하세요.

## 2026-09-29 QA 보완 검증

`fix/qa-findings`의 코드 커밋 `c0d0fe3`, `4f0a906`, `90ac4ad`, `6dd87f9`를
포함하는 `35ba8bb`에서 로컬 검증했다. 실제 .env·운영 DB·외부 AI·배포 서비스는 사용하지 않았다.

| 검증 | 결과 |
| --- | --- |
| `.venv/bin/python -m pytest -q` (backend에서 실행) | 148 passed, 경고 1개, 9.40초 |
| `node --test tests/frontend/*.test.cjs` (backend에서 실행) | 12 passed |
| 배포 설정 검사 셸 블록 로컬 실행 | 0.0/nan/inf/1e999 차단, 0.5/30 통과 |
| `git diff develop --check` | 통과 |
| README·TEAM 상대 링크 및 대표 커밋 존재 | 확인 |

Node 테스트는 추가 npm 패키지 없이 Node.js 22 이상에서 실행한다. 앱 실행에 Node는 필요하지 않다.
Python 경고는 기존 Starlette 테스트 클라이언트의 anyio BlockingPortal 별칭 폐기 예정 안내다.

### 추가한 회귀 검증

- AI가 null/배열/누락된 message/숫자·배열 content/공백/손상된 JSON을 반환하면
  502와 사용자 안내를 반환하고 실패 로그를 남긴다. 대화는 저장하지 않으며 다음 정상 요청은 복구된다.
- `AI_TIMEOUT`은 유한한 양수만 허용한다. 앱과 배포 사전 검사가
  `backend/app/config_validation.py`를 공유한다. 기본 30초와 정상 소수 값은 유지한다.
- 로그아웃은 204일 때만 이동한다. 200/401/403/500 및 네트워크 실패에서는
  오류 안내와 버튼 복구를 확인하고, 재시도 및 대기 중 중복 요청 차단을 검증한다.
- 조합 상태/isComposing/keyCode 229의 Enter는 전송하지 않는다.
  일반 Enter는 한 번 전송하고 Shift+Enter와 공백 입력은 전송하지 않는다.

### 로컬 브라우저 확인

임시 DB와 모의 AI를 사용하는 localhost 서버에서 첫 로그아웃 요청에만 HTTP 500을 주입했다.
실패 안내가 나타나고 /chat에 머물며 로그아웃 버튼을 다시 누를 수 있었다.
이후 정상 채팅, Shift+Enter 줄바꿈, 일반 Enter 전송, 로그아웃 재시도 성공을 확인했다.
로그아웃 후 /history 직접 접근은 /login으로 이동했다. 오류 주입은 임시 실행 스크립트에서만 사용했다.

실제 OS 한글 입력기로 발생하는 composition 이벤트 순서는 이 자동화에서 재현하지 않았다.
IME 처리는 JS 이벤트 단위 테스트로 확인했으며, Windows/macOS의 실제 한글 조합 확정 동작은
리뷰 시 수동으로 추가 확인한다. 외부 접근성·실제 AI 응답·OCI 배포 성공도 이번 검증 범위 밖이다.

### 변경하지 않은 정책

로그아웃 전에 복사한 서명 쿠키는 만료 전까지 재사용할 수 있다. 이는 [인증 정책](AUTH.md)의
서버 측 개별 세션 철회 미지원 범위이며, UI의 로그아웃 실패 무시 결함과는 별개다.

### PR 게시 전 확인

현재 워크플로는 같은 저장소의 develop/main 대상 PR에서도 OCI 배포를 수행한다.
로컬 테스트 통과는 배포 완료를 의미하지 않는다. 이 검증에서는 push·PR 게시·배포를 수행하지 않았다.
