# 프론트엔드&배엔드
프론트엔드는 사용자가 직접 보고 상호작용하는 화면 영역이며, 백엔드는 보이지 않는 곳에서 데이터를 처리하고 저장하는 서버 영역입니다.

**프론트엔드 (Frontend)**

* **역할**: 웹 브라우저에 표시되는 화면의 구조와 디자인, 그리고 [클릭, 입력, 화면 변경 등의 사용자 동작](https://github.com/nttkor/Codyssey-TermProject/blob/nttkor/study/frontend-backend-communication-flow.md#1-html-css-javascript%EC%9D%98-%EC%97%AD%ED%95%A0)을 담당합니다.
* **주요 기술**: [HTML, CSS, JavaScript](https://github.com/nttkor/Codyssey-TermProject/blob/nttkor/study/frontend-backend-communication-flow.md#1-html-css-javascript%EC%9D%98-%EC%97%AD%ED%95%A0) 등을 사용합니다.
* **비유**: 집의 뼈대(벽과 문), 인테리어 디자인, 그리고 전등을 켜고 끄는 스위치 겉면에 해당합니다.

**백엔드 (Backend)**

* **역할**: 로그인 인증, 데이터베이스 조회 및 저장, 외부 AI 연동 등 사용자 눈에 보이지 않는 서버 측의 모든 데이터 처리와 로직을 담당합니다.
* **주요 기술**: 보고 계신 문서에 언급된 [FastAPI](https://github.com/nttkor/Codyssey-TermProject/blob/nttkor/study/frontend-backend-communication-flow.md#1-html-css-javascript%EC%9D%98-%EC%97%AD%ED%95%A0)를 비롯해 Java, Node.js, 데이터베이스 등을 사용합니다.
* **비유**: 집의 벽 뒤에 숨겨져 실제 전기를 공급하고 물을 끌어오는 전기 배선이나 수도관 시스템에 해당합니다.

즉, 사용자가 프론트엔드(화면)에서 특정 요청을 보내면, 백엔드(서버)가 해당 요청을 분석해 데이터를 가공한 뒤 다시 프론트엔드로 전달하여 화면에 결과를 띄워주는 흐름으로 동작합니다.

# 프론트엔드와 백엔드 통신 흐름

이 문서는 AskMate 프로젝트를 예시로, 사용자가 실제 배포된 공인 IP 주소인 **`http://134.185.97.62/`** 에 접속한 순간부터 최초 리다이렉트, 로그인 화면 로딩, 로그인 수행, `/chat` 채팅 화면 진입, 질문 전송과 AI 답변 표시, 로그아웃까지의 **전체 프론트엔드-백엔드-인프라 통신 흐름**을 알기 쉽게 설명한다.

## 1. HTML, CSS, JavaScript의 역할

| 기술 | 역할 |
| --- | --- |
| HTML | 입력창, 버튼, 채팅 영역 등 화면의 구조를 만든다. |
| CSS | 색상, 크기, 배치 등 화면의 모양을 꾸민다. |
| JavaScript | 클릭, 입력, 서버 요청, 화면 변경 등 동작을 담당한다. |
| FastAPI | 로그인 확인, 데이터베이스 조회, AI 호출, 응답 반환을 담당한다. |

집에 비유하면 HTML은 벽과 문, CSS는 인테리어, JavaScript는 문을 열고 전등을 켜는 기능에 해당한다.

HTML은 JavaScript 없이도 링크 이동이나 일반적인 폼 제출을 할 수 있다. 하지만 JavaScript를 사용하면 페이지 전체를 새로고침하지 않고 서버와 통신하고, 현재 화면의 일부만 바꿀 수 있다.

## 2. HTML과 JavaScript 파일은 어떻게 연결되는가

HTML은 `script` 태그를 통해 JavaScript 파일을 불러온다.

```html
<script src="/static/js/common.js" defer></script>
<script src="/static/js/chat.js" defer></script>
```

브라우저가 HTML에서 이 코드를 발견하면 JavaScript 파일을 추가로 요청한다.

```text
GET /chat
├── GET /static/css/style.css
├── GET /static/js/common.js
└── GET /static/js/chat.js
```

`defer`는 HTML 구조를 먼저 읽은 뒤 JavaScript를 실행하라는 의미다.

HTML은 요소에 `id`를 지정한다.

```html
<form id="chatForm">
    <textarea id="chatInput"></textarea>
    <button id="chatSendBtn" type="submit">전송</button>
</form>
```

JavaScript는 같은 `id`를 사용해 HTML 요소를 찾는다.

```javascript
const form = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("chatSendBtn");
```

이후 클릭이나 폼 제출 같은 이벤트에 실행할 동작을 연결한다.

```javascript
form.addEventListener("submit", async (event) => {
    // 질문 전송 코드
});
```

이 단계에서는 아직 AI를 호출하지 않는다. 나중에 사용자가 질문을 전송했을 때 실행할 동작만 준비한다.

---

## 3. 사용자가 `http://134.185.97.62/` 에 처음 접속했을 때 일어나는 일

사용자가 웹 브라우저 주소창에 `http://134.185.97.62/` 를 입력하고 엔터를 누르면, 화면에 로그인 페이지가 나타나기까지 인터넷 네트워크, 클라우드 인프라, 백엔드 서버, 프론트엔드 브라우저 사이에서 다음과 같은 일들이 순차적으로 일어난다.

### 3.1 네트워크와 OCI 클라우드 인프라 전달

1. **HTTP 프로토콜과 80번 기본 포트**:
   * 브라우저는 프로토콜이 `http://`이고 포트 번호가 생략되어 있으므로, 기본 웹 포트인 **`80`번 포트**로 접속을 시도한다 (`134.185.97.62:80`).
2. **OCI(Oracle Cloud Infrastructure) 네트워크 도달**:
   * 요청 패킷은 인터넷 망을 거쳐 OCI 서울 리전에 생성된 가상 머신(Compute Instance)의 공인 IP `134.185.97.62`에 도착한다.
   * OCI 가상 클라우드 네트워크(VCN)의 **Security List(보안 목록)**에서 `80`번 포트 인바운드 허용 규칙을 통과한다.
   * VM 인스턴스 내부의 리눅스 방화벽(`iptables` / `ufw`)을 통과한다.
3. **Docker 컨테이너 포트 포워딩**:
   * OCI 호스트 서버에는 AskMate Docker 컨테이너가 포트 바인딩(`-p 80:8000`)으로 실행 중이다.
   * 호스트의 80번 포트로 들어온 요청은 컨테이너 내부의 `8000`번 포트에서 실행 중인 **Uvicorn(ASGI 웹 서버)** 프로세스로 전달된다.

### 3.2 최초 루트 요청(`GET /`)과 첫 번째 리다이렉트 (307 Temporary Redirect)

```text
[브라우저]                                    [FastAPI 서버 (pages.py)]
    │                                                    │
    ├───────────── 1. GET / (세션 쿠키 없음) ───────────→│
    │                                                    │ index() 실행
    │←─── 2. HTTP 307 Temporary Redirect (Location: /login) ┤
```

* 사용자가 브라우저에 입력한 경로는 루트(`/`)다.
* FastAPI의 `pages.py`에 정의된 라우터가 이 요청을 받는다.
  ```python
  @router.get("/", response_class=HTMLResponse)
  def index():
      return RedirectResponse(url="/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
  ```
* 서버는 HTML 문서를 내려주지 않고, 브라우저에게 **`HTTP 307 Temporary Redirect`** 응답과 함께 헤더에 `Location: /login`을 전달한다.
* 이 응답을 받은 브라우저는 자동으로 주소창을 `http://134.185.97.62/login`으로 변경하며 다음 요청을 즉시 보낸다.

### 3.3 로그인 화면 요청(`GET /login`)과 서버의 비로그인 상태 확인

```text
[브라우저]                                    [FastAPI 서버 (pages.py)]
    │                                                    │
    ├─────────── 3. GET /login (세션 쿠키 검사) ─────────→│
    │                                                    │ login_page() 실행
    │                                                    │ - 세션 없음 (user is None)
    │                                                    │ - Jinja2: login.html 렌더링
    │←────────── 4. HTTP 200 OK (완성된 HTML 전달) ───────┤
```

* 브라우저는 즉시 `GET /login` 요청을 서버에 전송한다.
* FastAPI의 `SessionMiddleware`와 `auth.py`의 `get_session_user`가 요청 헤더에 세션 쿠키(`askmate_session`)가 있는지 확인한다:
  * **처음 접속한 비로그인 상태**: 쿠키가 없으므로 `user`는 `None`이다.
  * `pages.py`의 `login_page()` 함수가 실행된다:
    ```python
    @router.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, user: Annotated[User | None, Depends(get_session_user)]):
        if user:
            return RedirectResponse(url="/chat", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse(request=request, name="login.html", context={"user": None})
    ```
* **Jinja2 템플릿 엔진**이 서버 메모리에서 동작한다:
  * `templates/login.html`은 `templates/base.html`을 상속받아 하나의 완전한 HTML을 구성한다.
  * `user`가 `None`이므로 상단 네비게이션 메뉴에는 채팅/로그아웃 버튼 대신 기본 로고와 로그인/회원가입 메뉴만 배치된다.
* 서버는 이 완성된 HTML 텍스트를 `HTTP 200 OK` 상태 코드와 함께 브라우저로 전송한다.

> **💡 만약 이미 로그인된 상태에서 접속했다면?**
> 브라우저에 유효한 세션 쿠키가 저장되어 있다면, 서버는 `user` 객체를 확인하고 로그인 화면을 보여주는 대신 **`HTTP 303 See Other (Location: /chat)`** 로 즉시 `/chat` 화면으로 이동시킨다!

### 3.4 브라우저의 HTML 수신과 정적 자원(CSS, JS) 연쇄 다운로드

브라우저는 전달받은 HTML을 위에서부터 한 줄씩 읽어 내려가며 화면을 그리기 시작한다. 이 과정에서 필요한 CSS와 JavaScript 파일을 발견하고 서버에 연쇄적으로 요청한다.

```text
GET http://134.185.97.62/login
  ├── GET /static/css/style.css       → 디자인 스타일 시트 다운로드
  ├── GET /static/js/common.js        → 공통 자바스크립트 다운로드
  └── GET /static/js/login.js         → 로그인 전용 자바스크립트 다운로드
```

1. `<link rel="stylesheet" href="/static/css/style.css">`:
   * 스타일시트를 다운로드하여 폰트, 색상, 카드 레이아웃, 버튼 디자인을 적용한다.
2. `<script src="/static/js/common.js" defer>` 및 `<script src="/static/js/login.js" defer>`:
   * 스크립트 파일을 비동기로 다운로드한다.
   * `defer` 속성이 있으므로 **HTML 파싱이 완전히 끝날 때까지 실행을 대기**하여 화면이 하얗게 멈추는 현상을 방지한다.

### 3.5 브라우저 DOM 완성 및 JavaScript 이벤트 활성화

HTML 파싱이 끝나고 화면의 요소(DOM)가 모두 준비되면 브라우저에서 `DOMContentLoaded` 이벤트가 발생하며 JavaScript가 활성화된다.

1. **비밀번호 토글 기능 활성화 (`common.js`)**:
   * `initPasswordToggles()`가 실행되어 비밀번호 입력창 우측의 눈 모양 아이콘을 찾는다.
   * 클릭 시 `type="password"`와 `type="text"`를 전환하여 비밀번호를 보이거나 숨길 수 있도록 클릭 이벤트를 연결한다.
2. **가입 완료 안내 확인 (`login.js`)**:
   * `new URLSearchParams(window.location.search)`를 통해 URL에 `?registered=1` 파라미터가 있는지 검사한다.
   * 만약 회원가입을 마치고 넘어온 상태라면 상단에 "회원가입이 완료되었습니다. 로그인해 주세요."라는 녹색 알림 메시지를 표시한다.
3. **로그인 폼 제출 이벤트 가로채기 (`login.js`)**:
   * 로그인 폼(`#loginForm`)에 `submit` 이벤트 리스너를 등록한다.
   * 사용자가 [로그인] 버튼을 누르거나 비밀번호 창에서 Enter를 쳤을 때, 기본 페이지 새로고침을 막고 비동기 API(`POST /api/login`)를 호출할 준비를 마친다.
4. **최종 상태**:
   * 이제 화면에는 사용자명과 비밀번호를 입력할 수 있는 깔끔한 로그인 카드가 렌더링되어 사용자의 입력을 대기한다.

### 3.6 로그인 성공 시 `/chat` 화면으로의 전환

사용자가 사용자명과 비밀번호를 입력하고 [로그인] 버튼을 누르면:

```text
[브라우저 (login.js)]                               [FastAPI 서버 (account.py)]
    │                                                            │
    ├─────── POST /api/login {"username":"..","password":".."} ──→│
    │                                                            │ 1. Argon2 비밀번호 검증
    │                                                            │ 2. request.session["user_id"] 저장
    │←────── HTTP 200 OK (Set-Cookie: askmate_session=...) ──────┤
    │
    │ 3. login.js가 200 OK 확인 후 페이지 이동
    ├─────── window.location.assign("/chat") ───────────────────→ 브라우저가 /chat으로 이동
```

1. 프론트엔드가 JSON 형식으로 `POST /api/login`을 호출한다.
2. 서버는 Argon2 해시를 검증하고, 일치하면 사용자 ID를 세션에 담아 **암호화 서명된 `askmate_session` 쿠키**를 발급한다.
3. 로그인이 성공하면 `login.js`가 `window.location.assign("/chat")`을 실행하여 채팅 화면으로 진입한다.

---

## 4. 로그인 후 `/chat` 화면에 접속했을 때

로그인에 성공한 사용자는 브라우저에서 `/chat` 주소로 이동하게 된다. (로컬 환경은 `http://127.0.0.1:8000/chat`, 배포 환경은 `http://134.185.97.62/chat`)

### 4.1 브라우저가 HTML 화면을 요청한다

```text
브라우저 → GET /chat → FastAPI 서버
```

브라우저는 3단계에서 로그인 성공 시 발급받았던 세션 쿠키를 요청 헤더에 자동으로 실어서 전송한다.

```http
GET /chat
Cookie: askmate_session=...
```

### 4.2 서버가 로그인 여부를 확인한다

FastAPI는 세션 쿠키에서 사용자 ID를 확인하고 데이터베이스에서 사용자를 조회한다.

로그인하지 않은 경우:

```text
GET /chat
→ 로그인 사용자 없음
→ 303 /login 응답
→ 브라우저가 /login으로 이동
```

로그인한 경우:

```text
GET /chat
→ 세션에서 사용자 ID 확인
→ 데이터베이스에서 사용자 조회
→ chat.html 생성
→ 브라우저에 HTML 반환
```

서버는 Jinja2 템플릿에 사용자 정보를 넣어 완성된 HTML을 만든다.

템플릿:

```html
안녕하세요, <strong>{{ user.username }}</strong>님!
```

사용자명이 `minsu`인 경우 브라우저가 받는 결과:

```html
안녕하세요, <strong>minsu</strong>님!
```

### 4.3 브라우저가 CSS와 JavaScript를 요청한다

브라우저는 받은 HTML을 분석한다. HTML 안에서 CSS와 JavaScript 파일 참조를 발견하면 해당 파일을 서버에 추가로 요청한다.

```text
chat.html  → 입력창, 전송 버튼, 채팅 영역 생성
style.css  → 채팅 화면의 디자인 적용
common.js  → 공통 API 요청과 로그아웃 기능 준비
chat.js    → 질문 전송과 답변 표시 기능 준비
```

### 4.4 JavaScript가 이벤트를 연결한다

`chat.js`는 화면의 폼, 입력창, 전송 버튼을 찾아 변수에 저장한다.

```javascript
const form = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("chatSendBtn");
```

그리고 폼이 제출될 때 실행할 함수를 등록한다.

```javascript
form.addEventListener("submit", async (event) => {
    // 전송 버튼을 눌렀을 때 실행된다.
});
```

이 단계에서는 아직 AI를 호출하지 않는다. 나중에 사용자가 질문을 전송했을 때 실행할 동작만 준비한다.

---

## 5. 사용자가 질문을 전송했을 때

### 5.1 전송 버튼과 Enter 키 입력 (`submit` 이벤트)

전송 버튼은 다음과 같이 `type="submit"`으로 정의되어 있다.

```html
<button type="submit" id="chatSendBtn">전송</button>
```

버튼을 누르면 버튼이 속한 `form`의 `submit` 이벤트가 발생한다. 입력창(`textarea`)에서 Enter를 눌러도 자바스크립트 `keydown` 이벤트를 통해 폼 제출을 실행할 수 있다.

> **💡 한글 입력(IME 조합)과 Enter 오작동 방지**:
> 한글, 일본어 등은 자음과 모음이 합쳐지는 **조합 문자(IME)**다. 사용자가 한글 입력을 마치고 글자를 확정 짓기 위해 Enter를 누르는 순간, 브라우저는 아직 글자를 조합 중(`compositionstart` ~ `compositionend`)으로 인식할 수 있다.
> 만약 이를 그대로 전송하면 **마지막 글자가 중복되거나 미완성된 상태에서 질문이 의도치 않게 전송**된다.
> 따라서 `chat.js`는 다음 조건을 확인하여 조합 확정용 Enter는 전송을 무시하도록 방어한다.
> ```javascript
> if (isComposing || e.isComposing || e.keyCode === 229) return;
> ```
> 또한 `Shift + Enter`는 전송하지 않고 텍스트 에어리어에서 줄바꿈을 유지하도록 처리한다.

### 5.2 일반적인 HTML 폼 제출을 중단한다

일반적인 HTML 폼은 제출되면 새로운 페이지로 이동한다. 현재 프로젝트에서는 JavaScript가 이 기본 동작을 막는다.

```javascript
form.addEventListener("submit", async (event) => {
    event.preventDefault();
});
```

`event.preventDefault()` 때문에 현재 `/chat` 페이지가 다른 페이지로 바뀌지 않는다.

### 5.3 JavaScript가 현재 화면에 질문을 표시한다

JavaScript는 사용자의 질문을 채팅 영역에 말풍선으로 추가하고, AI가 답변 중이라는 로딩 표시를 보여준다.

```text
👤 FastAPI가 뭐야?
🤖 ···
```

이때 서버에서 새로운 HTML 문서를 받은 것이 아니다. JavaScript가 브라우저 메모리에 있는 현재 DOM에 요소를 추가한 것이다.

```javascript
const bubble = document.createElement("div");
bubble.textContent = question;
messagesContainer.appendChild(bubble);
```

---

## 6. JavaScript가 백엔드 API를 호출한다

JavaScript는 `fetch()`를 이용해 현재 페이지 뒤에서 별도의 HTTP 요청을 보낸다.

```javascript
const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest"
    },
    body: JSON.stringify({
        question: "FastAPI가 뭐야?"
    })
});
```

실제 요청은 다음과 비슷하다.

```http
POST /api/chat
Cookie: askmate_session=...
Content-Type: application/json
X-Requested-With: XMLHttpRequest

{"question":"FastAPI가 뭐야?"}
```

여기서 `/chat`과 `/api/chat`은 역할이 다르다.

| 요청 | 역할 |
| --- | --- |
| `GET /chat` | 최초 채팅 HTML 화면을 제공한다. |
| `POST /api/chat` | 질문을 받아 AI 답변 데이터를 제공한다. |

`fetch()`도 정상적인 HTTP 요청이다. 다만 브라우저가 응답을 새 페이지로 표시하지 않고, JavaScript가 응답을 데이터로 받는다는 차이가 있다.

## 7. 백엔드가 질문을 처리한다

FastAPI 서버는 `POST /api/chat` 요청을 받으면 다음 순서로 처리한다.

```text
1. CSRF 헤더 검사 (X-Requested-With: XMLHttpRequest)
2. 로그인 세션 확인 (get_current_user)
3. 질문 본문 검증 (1~1,000자, 공백만 있는 문자열 차단)
4. 현재 사용자의 최근 대화 5쌍을 DB에서 조회 (오름차순 문맥)
5. 최근 대화와 현재 질문을 AsyncOpenAI 클라이언트로 전송
6. AI 응답 수신 및 안전성 검증:
   ├── OpenAIError / JSON 파싱 에러(JSONDecodeError) 발생 시 → 502 변환
   ├── choices 누락, content 타입 불일치(문자열 아님) 등 비정상 페이로드 → 502 (InvalidAnswer)
   └── content가 빈 문자열("")인 경우 → 502 (EmptyAnswer)
7. 성공적으로 검증된 질문과 답변만 SQLite DB에 저장 (chat_db.create_chat)
8. JSON 응답 반환 {"answer": "..."}
```

응답은 전체 HTML이 아니라 데이터만 포함한 JSON이다.

```json
{
  "answer": "FastAPI는 Python 기반 웹 프레임워크입니다."
}
```

> **🛡️ AI 통신 실패 시 DB 미저장 원칙**:
> AI 호출에 실패(502/504)하거나 비정상/빈 답변을 받으면 **질문과 답변을 데이터베이스에 저장하지 않는다.**
> 또한 외부 AI 제공자의 상세 오류나 API 키는 사용자 응답에 절대 포함하지 않고, 안전하게 추상화된 한국어 안내문구만 전달한다.

---

## 8. `response`와 화면 변경의 관계

`response`는 함수가 아니다. 서버에서 받은 HTTP 응답을 표현하는 객체다.

```javascript
const response = await fetch("/api/chat", options);
```

`response`에서는 상태 코드와 성공 여부 등을 확인할 수 있다.

```javascript
response.status; // 예: 200
response.ok;     // 예: true
```

JSON 본문은 별도로 읽어야 한다.

```javascript
const data = await response.json();
```

서버가 다음 JSON을 반환했다면:

```json
{"answer":"안녕하세요!"}
```

JavaScript에서는 다음과 같이 답변을 꺼낸다.

```javascript
data.answer; // "안녕하세요!"
```

화면을 바꾸는 것은 `response` 객체가 아니라, 응답 데이터를 받은 뒤 실행되는 JavaScript 함수다.

```javascript
appendMessage("ai", data.answer);
```

```text
fetch()가 서버에 요청
→ response 객체에 HTTP 응답 저장
→ response.json()으로 JSON 읽기
→ data.answer에서 답변 꺼내기
→ appendMessage()가 HTML 요소 생성
→ 현재 채팅 영역에 요소 추가
```

---

## 9. 페이지 전체를 새로고침하지 않는 원리

일반적인 HTML 폼 제출 방식은 다음과 같다.

```text
POST /chat
→ 서버가 완성된 HTML 전체 반환
→ 기존 문서 제거
→ 새 HTML 분석
→ 전체 화면 다시 표시
```

JavaScript의 `fetch()` 방식은 다음과 같다.

```text
POST /api/chat
→ 서버가 JSON 데이터 반환
→ 기존 HTML 문서 유지
→ JavaScript가 채팅 영역만 변경
```

이를 가능하게 하는 핵심 코드는 다음 두 가지다.

```javascript
event.preventDefault(); // 일반적인 폼 제출과 페이지 이동 방지
fetch(...);             // 현재 페이지 뒤에서 별도 HTTP 요청
```

응답을 받은 후 DOM API로 현재 화면의 일부만 변경한다.

```javascript
messagesContainer.appendChild(newMessage);
```

HTML 파일 자체가 수정되는 것은 아니다. 브라우저 메모리에 만들어진 현재 DOM만 변경된다. 페이지를 새로고침하면 서버에서 HTML을 다시 받아 처음 상태에서 시작한다.

---

## 10. 전체 통신 흐름

### 10-1. 배포 주소 최초 접속부터 로그인까지의 흐름 (`http://134.185.97.62/`)

```text
[사용자 브라우저]                                    [OCI 서버 (Docker / FastAPI)]
       │                                                          │
       ├──── 1. 브라우저 주소창에 http://134.185.97.62/ 입력 ────→│ (80번 포트 → Docker 8000 전달)
       │                                                          │
       │←─── 2. HTTP 307 Temporary Redirect (Location: /login) ───┤ pages.index() 실행
       │                                                          │
       ├──── 3. GET /login 요청 (세션 쿠키 없음) ────────────────→│
       │                                                          │ pages.login_page() 실행
       │                                                          │ Jinja2: base.html + login.html 렌더링
       │←─── 4. HTTP 200 OK (완성된 로그인 HTML 반환) ────────────┤
       │                                                          │
       ├──── 5. 브라우저가 CSS 및 JS 추가 요청 ───────────────────→│
       │        (GET /static/css/style.css, /static/js/*.js)      │ StaticFiles가 파일 전송
       │←─── 6. HTTP 200 OK (CSS/JS 정적 파일 수신) ──────────────┤
       │
       │ (브라우저 DOM 완성 및 common.js, login.js 이벤트 등록 완료)
       │ (사용자가 아이디/비밀번호 입력 후 [로그인] 클릭)
       │
       ├──── 7. POST /api/login {"username":"..", "password":".."}→│ account.login() 실행
       │        (CSRF 헤더 포함, preventDefault로 비동기 전송)    │ Argon2 비밀번호 검증 & 세션 생성
       │←─── 8. HTTP 200 OK (Set-Cookie: askmate_session=...) ────┤
       │
       │ (login.js가 window.location.assign("/chat") 실행)
       └──── 9. 브라우저가 http://134.185.97.62/chat 으로 이동 ──→ 채팅 화면 진입
```

### 10-2. 질문 및 답변 통신 흐름

```text
브라우저에서 /chat 접속 (세션 쿠키 보유)
        ↓
FastAPI가 로그인 세션 확인 후 chat.html 렌더링 반환
        ↓
브라우저가 chat.js 로드 및 이벤트 바인딩 (IME 조합 및 Enter 처리)
        ↓
사용자가 질문 입력 후 Enter/전송 클릭
        ↓
event.preventDefault()로 페이지 이동 방지
        ↓
JavaScript가 POST /api/chat 요청 (JSON 본문 + CSRF 헤더)
        ↓
FastAPI가 DB에서 최근 대화 5쌍 조회 (문맥 구성)
        ↓
외부 AI 서비스(AsyncOpenAI) 호출 및 안전한 응답 유효성 검증
        ↓
정상 응답 시 질문·답변 한 쌍을 SQLite DB에 저장 (실패 시 미저장 & 502/504)
        ↓
JSON 응답 반환 {"answer": "..."}
        ↓
JavaScript가 JSON에서 답변 텍스트 추출
        ↓
현재 채팅 화면 DOM에 답변 말풍선 추가 (오류 시 재시도 버튼 표시)
```

### 10-3. 로그아웃 통신 흐름과 안정성 보장 (`POST /api/logout`)

상단 메뉴의 로그아웃 동작은 단순 링크 이동이 아니라 비동기 API 요청을 통해 세션을 파기하고 결과를 검증한다.

```text
사용자가 상단 로그아웃 버튼(#navLogoutBtn) 클릭
        ↓
로그아웃 버튼 잠금 (disabled = true, 중복 요청 차단)
기존 로그아웃 에러 배너(#logoutError) 숨김
        ↓
common.js가 POST /api/logout 비동기 요청 (CSRF 헤더 포함)
        ↓
FastAPI 서버: 세션 초기화 (request.session.clear())
        ↓
HTTP 204 No Content 응답 반환
        ↓
브라우저 검증:
  ├── [204 성공] → window.location.assign("/login") 으로 안전하게 이동
  └── [실패(200, 401, 500, 네트워크 단절)]
        ├─ 화면 이동 없이 현재 페이지 유지 (오작동 착각 방지)
        ├─ #logoutError 배너 표시: "로그아웃에 실패했습니다. 다시 시도해 주세요."
        └─ finally 블록에서 버튼 잠금 해제 (disabled = false) → 즉시 재시도 가능
```

---

## 11. 핵심 요약

- **배포 주소 접속 (`http://134.185.97.62/`)**:
  - 기본 HTTP 포트인 80번 포트로 OCI 호스트에 접근하여 Docker 포트포워딩을 통해 컨테이너 내부 Uvicorn(8000)으로 전달된다.
  - 최초 루트 요청(`GET /`)은 서버의 `307 Temporary Redirect`에 의해 `/login`으로 자동 이동된다.
  - 비로그인 상태는 `login.html`이 렌더링되고, 이미 로그인된 상태는 `303 See Other`에 의해 `/chat`으로 자동 직행한다.
- **HTML, CSS, JS 분업**:
  - HTML은 최초 화면의 구조를 만들고, CSS는 화면의 모양을 꾸민다.
  - JavaScript는 사용자의 행동과 서버 API를 비동기로 연결하여 화면의 일부분만 동적으로 바꾼다.
- **안전한 한글 입력**:
  - 한글 자모 조합 중(IME `isComposing`) 누르는 Enter는 질문 전송을 차단하여 글자 중복과 오작동을 방지한다.
- **데이터베이스 저장 원칙**:
  - AI 호출이 성공하고 응답 검증을 통과했을 때만 질문과 답변을 SQLite DB에 저장한다. AI 오류 시에는 저장하지 않는다.
- **로그아웃 안전성**:
  - 로그아웃은 서버 응답이 204 성공일 때만 페이지를 이동하며, 실패 시 에러 안내와 재시도를 지원한다.

