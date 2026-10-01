# 프론트엔드 & 백엔드
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
과거에는 HTML 태그 안에 직접 `onclick="전송함수()"`처럼 자바스크립트 동작을 섞어서 작성하기도 했지만, 현대 웹 개발에서는 방금 파악하신 것처럼 **HTML에는 뼈대와 식별자(`id`, `class`)만 남겨두고, 실제 동작은 자바스크립트 파일에서 따로 `addEventListener`로 연결해 주는 방식**을 표준으로 사용합니다.

이를 개발 용어로 '관심사의 분리(Separation of Concerns)'라고 부릅니다. 코드를 목적에 맞게 분리해 두면 유지보수하기가 훨씬 쉬워지기 때문입니다.

추가로 눈여겨보실 점은 버튼 태그에 있는 `type="submit"` 속성입니다.
버튼에 이 속성이 있으면 사용자가 버튼을 클릭했을 때 브라우저가 알아서 버튼이 속한 `<form>` 전체를 제출(submit)하려는 이벤트를 발생시킵니다.

그래서 [문서의 4.4 항목](https://github.com/nttkor/Codyssey-TermProject/blob/nttkor/study/frontend-backend-communication-flow.md#44-javascript%EA%B0%80-%EC%9D%B4%EB%B2%A4%ED%8A%B8%EB%A5%BC-%EC%97%B0%EA%B2%B0%ED%95%9C%EB%8B%A4)을 보면, 자바스크립트가 버튼 자체의 `click` 이벤트를 감지하는 대신 폼(form)의 `submit` 이벤트를 감지하도록 `form.addEventListener("submit", ...)` 형태로 작성되어 있는 것을 확인할 수 있습니다.

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

## 11. 웹 통신 및 대화 처리 1~5단계 기술 심층 분석 (파일명 및 주요 코드 스니펫)

AskMate의 사용자 인터랙션부터 AI 응답 출력, 그리고 안전한 로그아웃에 이르는 1~5단계 전체 흐름을 프론트엔드와 백엔드의 구체적인 파일명, 함수/라우터명, 실제 소스코드 스니펫과 함께 상세히 분석한다.

---

### 1단계: 초기 렌더링 및 화면 구성

사용자가 브라우저 주소창에 `/chat`을 입력하거나 로그인 성공 후 이동할 때, 서버가 세션을 검증하고 Jinja2 템플릿을 통해 개인화된 HTML 문서를 생성하여 응답하는 단계이다.

#### 1. 관련 파일 및 주요 심볼
- **백엔드 라우터**: `backend/app/pages.py`의 `chat_page`
- **인증 의존성**: `backend/app/auth.py`의 `get_session_user`
- **Jinja2 템플릿**:
  - `backend/app/templates/base.html` (공통 레이아웃 및 네비게이션)
  - `backend/app/templates/chat.html` (채팅 전용 화면 구조)

#### 2. 핵심 소스코드 스니펫

##### [백엔드] `backend/app/pages.py` - 세션 검증 및 303 Redirect / Jinja2 렌더링
```python
@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, user: Annotated[User | None, Depends(get_session_user)]):
    """AI 대화창 HTML 화면을 렌더링합니다. 로그인이 필요한 보호된 페이지입니다.

    [기술 설명]
    1. 비로그인 상태(`user is None`)인 경우 접근을 제한하고 `/login`으로 303 리다이렉트합니다.
    2. 로그인 상태인 경우 사용자 정보(`user`)를 템플릿 컨텍스트에 전달하여 네비게이션 바 등에
       사용자명이 표시될 수 있도록 렌더링합니다.
    3. `Cache-Control: no-store` 헤더를 설정하여 비인가 단말 캐싱을 방지합니다.
    """
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="chat.html", context={"user": user}, headers={"Cache-Control": "no-store"}
    )
```

##### [백엔드] `backend/app/auth.py` - 세션 쿠키 검증 및 고스트 세션 방어
```python
def get_session_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    """현재 요청의 쿠키 세션에서 사용자 식별자를 읽어 DB의 User 객체를 반환합니다."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        user = get_user_by_id(db, user_id)
    except SQLAlchemyError:
        logger.exception("db_read_failure operation=session")
        raise HTTPException(status_code=500, detail="로그인 정보를 확인하지 못했습니다.") from None
    if user is None:
        # DB에 사용자가 존재하지 않는데 세션만 남아있는 고스트 세션 상태 정리
        request.session.clear()
    return user
```

##### [템플릿 상속 및 변수 대입] `backend/app/templates/base.html` & `chat.html`
```html
<!-- base.html: 공통 상단 네비게이션 바 -->
<nav class="nav-menu" aria-label="주 메뉴">
    {% if user %}
    <a href="{{ url_for('chat_page') }}" class="nav-link {% if request.url.path == '/chat' %}active{% endif %}">채팅</a>
    <a href="{{ url_for('history_page') }}" class="nav-link {% if request.url.path == '/history' %}active{% endif %}">대화 기록</a>
    <div class="user-profile-menu">
        <span class="user-badge" title="로그인 사용자">
            <span class="user-avatar">👤</span>
            <strong class="user-name" id="navUsername">{{ user.username }}</strong>
        </span>
        <button type="button" class="btn btn-outline btn-sm logout-btn" id="navLogoutBtn">로그아웃</button>
    </div>
    {% else %}
    <!-- 비로그인 메뉴 -->
    {% endif %}
</nav>

<!-- chat.html: base.html을 상속받아 채팅 화면 구현 -->
{% extends "base.html" %}
{% block title %}채팅{% endblock %}
{% block content %}
<div class="chat-container">
    <div class="chat-card">
        <!-- 환영 메시지: Jinja2 변수({{ user.username }}) 치환 -->
        <div id="chatMessages" class="chat-messages" role="log" aria-live="polite">
            <div class="chat-bubble ai-bubble intro-bubble">
                <div class="bubble-avatar">🤖</div>
                <div class="bubble-body">
                    <div class="bubble-author">AskMate AI</div>
                    <div class="bubble-content">안녕하세요, <strong>{{ user.username }}</strong>님! 무엇이든 편하게 물어보세요.</div>
                </div>
            </div>
        </div>
        ...
    </div>
</div>
{% endblock %}
```

#### 3. 핵심 동작 원리 및 보안 메커니즘
1. **세션 쿠키 검증**: 클라이언트가 보낸 `askmate_session` 서명 쿠키를 `SessionMiddleware`가 복호화하고, `get_session_user` 의존성이 세션 내부의 `user_id`를 추출하여 DB에서 실제 유저를 조회한다.
2. **보호된 라우트 및 HTTP 303 Redirect**: 비인가 사용자(`user is None`)가 `/chat`에 직접 접근하면 서버는 즉시 `303 See Other` 상태 코드와 함께 `Location: /login` 헤더를 반환하여 로그인 페이지로 안전하게 튕겨낸다.
3. **템플릿 컨텍스트 바인딩**: 인증된 사용자인 경우 `context={"user": user}`를 전달하여, Jinja2 엔진이 서버 사이드에서 `{{ user.username }}`을 실제 사용자명(예: `minsu`)으로 치환한 완전한 HTML 텍스트를 생성하여 전송한다.
4. **캐싱 방지 (`Cache-Control: no-store`)**: 개인정보가 포함된 동적 HTML 페이지가 브라우저나 중간 프록시 캐시에 영구 저장되지 않도록 강제하여 공용 PC에서의 뒤로가기 정보 유출을 차단한다.

---

### 2단계: 폼 이벤트 등록 및 자바스크립트 제어

브라우저가 HTML을 파싱하고 `DOMContentLoaded` 이벤트가 발생하면, `chat.js`가 로드되어 DOM 요소를 탐색하고 사용자 입력(글자 수 제한, 한글 IME 조합 처리, 단축키)을 제어하는 이벤트 리스너를 바인딩한다.

#### 1. 관련 파일 및 주요 심볼
- **프론트엔드 스크립트**: `backend/app/static/js/chat.js`
- **주요 함수/이벤트**:
  - `updateCharCounter()`: 실시간 글자 수 카운팅 및 1,000자 초과 방어
  - `chatInput.addEventListener("compositionstart" / "compositionend")`: 한글 IME 조합 상태 추적
  - `chatInput.addEventListener("keydown")`: Enter 단독 전송 / `Shift + Enter` 줄바꿈 분기
  - `form.addEventListener("submit")`: `event.preventDefault()` 기본 폼 제출 차단

#### 2. 핵심 소스코드 스니펫

##### [프론트엔드] `backend/app/static/js/chat.js` - DOM 탐색, IME 조합 방어 및 글자 수 검증
```javascript
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chatForm");
    if (!form) return;

    // DOM 엘리먼트 참조
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSendBtn");
    const charCounter = document.getElementById("charCounter");

    // 상태 관리 플래그
    let isSubmitting = false;     // API 통신 진행 중 여부
    let isComposing = false;      // 한글/CJK IME 문자 조합 중 여부

    /**
     * 입력창 글자수 카운터를 갱신하고, 글자수 제한(1000자) 및 버튼 활성화 상태를 동기화합니다.
     */
    function updateCharCounter() {
        const length = chatInput.value.length;
        const trimmed = chatInput.value.trim();
        charCounter.textContent = `${length} / 1000자`;

        // 1000자 초과 시 경고 스타일 적용 및 전송 버튼 비활성화
        if (length > 1000) {
            charCounter.classList.add("limit-exceeded");
            sendBtn.disabled = true;
        } else {
            charCounter.classList.remove("limit-exceeded");
            // 전송 중이거나 공백만 있는 경우 전송 버튼 비활성화
            sendBtn.disabled = isSubmitting || trimmed.length === 0;
        }

        // 입력 텍스트 높이에 맞춘 textarea 동적 리사이징 (최대 160px)
        chatInput.style.height = "auto";
        chatInput.style.height = `${Math.min(chatInput.scrollHeight, 160)}px`;
    }

    // 입력 이벤트 및 IME 조합 상태 감지 리스너 바인딩
    chatInput.addEventListener("input", updateCharCounter);
    chatInput.addEventListener("compositionstart", () => { isComposing = true; });
    chatInput.addEventListener("compositionend", () => { isComposing = false; });

    /**
     * 키보드 단축키 이벤트:
     * - Enter 단독 입력 시 질문 전송
     * - Shift + Enter 입력 시 줄바꿈 허용
     * - 한글 조합 중(isComposing, keyCode 229) Enter는 전송을 무시
     */
    chatInput.addEventListener("keydown", (e) => {
        // IME 조합 확정 Enter는 전송이 아닙니다. 일부 브라우저는 keyCode 229만 전달하므로 함께 검사합니다.
        if (isComposing || e.isComposing || e.keyCode === 229) return;
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault(); // 기본 개행 방지
            if (!sendBtn.disabled) {
                // 폼의 submit 이벤트를 트리거하여 질문 전송 실행
                form.dispatchEvent(new Event("submit", { cancelable: true }));
            }
        }
    });
});
```

#### 3. 핵심 동작 원리 및 클라이언트 유효성 검증
1. **페이지 새로고침 방지 (`event.preventDefault()`)**: 폼이 제출될 때 브라우저의 기본 동작인 페이지 새로고침(Full Page Reload)을 차단하여 단일 페이지(SPA) 스타일의 매끄러운 사용자 경험을 유지한다.
2. **한글 IME 중복 전송 방어**:
   - 한글은 초성·중성·종성이 결합되는 조합 문자(IME)이므로, 글자 작성을 확정하기 위해 Enter를 누르면 브라우저에 따라 조합 확정용 `keydown`과 폼 제출 `keydown`이 연달아 발생하여 동일 질문이 2번 전송되거나 마지막 글자가 중복되는 버그가 발생한다.
   - `compositionstart`, `compositionend` 이벤트 플래그(`isComposing`), 표준 `e.isComposing`, 구형 브라우저 호환용 `e.keyCode === 229`를 삼중으로 체크하여 조합 중 Enter는 전송을 원천 차단한다.
3. **단축키 분기 (`Shift + Enter` vs `Enter`)**: `e.shiftKey`가 눌려있으면 텍스트 입력창 내 줄바꿈을 허용하고, `Enter` 단독일 때만 질문을 전송한다.
4. **실시간 글자 수 및 공백 검증**: `trim()`을 적용하여 공백 문자열만 입력된 경우 전송 버튼을 비활성화(`disabled = true`)하며, 1,000자를 초과하면 카운터에 경고 색상을 표시하고 전송을 막는다.

---

### 3단계: 메시지 전송 및 비동기 API 통신

사용자가 질문을 확정하면 프론트엔드가 CSRF 방어 헤더를 주입하여 백엔드로 비동기 HTTP 요청을 전송하고, 백엔드는 보안 인증, 입력값 유효성 검사, DB 문맥 조회(최근 5쌍), 비동기 OpenAI 연동까지의 AI 파이프라인을 실행한다.

#### 1. 관련 파일 및 주요 심볼
- **프론트엔드 비동기 래퍼**: `backend/app/static/js/common.js`의 `apiRequest`
- **백엔드 보안 가드**: `backend/app/auth.py`의 `require_csrf_header`, `get_current_user`
- **백엔드 AI 라우터**: `backend/app/llm.py`의 `ChatRequest`, `chat`
- **DB 문맥 조회 DAL**: `backend/app/chat_db.py`의 `get_recent_chats_by_user`
- **외부 AI 연동 모듈**: `backend/app/llm_connect.py`의 `generate_answer`, `AsyncOpenAI`

#### 2. 핵심 소스코드 스니펫

##### [프론트엔드] `backend/app/static/js/common.js` - `apiRequest` 래퍼 및 CSRF 헤더 자동 주입
```javascript
async function apiRequest(url, options = {}) {
    const defaultHeaders = {
        "Content-Type": "application/json",
    };

    // 상태 변경 요청(POST, PUT, DELETE)에 CSRF 방어 커스텀 헤더 필수 주입
    const method = (options.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
        defaultHeaders["X-Requested-With"] = "XMLHttpRequest";
    }

    options.headers = { ...defaultHeaders, ...(options.headers || {}) };

    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    }

    const response = await fetch(url, options);
    ...
    return { ok: response.ok, status: response.status, data: await response.json() };
}
```

##### [백엔드] `backend/app/auth.py` - CSRF 헤더 검증 및 엄격한 사용자 인증
```python
def require_csrf_header(
    requested_with: Annotated[str | None, Header(alias="X-Requested-With")] = None,
) -> None:
    """모든 상태 변경(POST) 요청에 대해 커스텀 헤더 존재 여부를 검증하여 CSRF를 방어합니다."""
    if requested_with != "XMLHttpRequest":
        raise HTTPException(status_code=403, detail="X-Requested-With: XMLHttpRequest 헤더가 필요합니다.")

def get_current_user(user: Annotated[User | None, Depends(get_session_user)]) -> User:
    """비로그인 상태일 경우 즉시 HTTP 401 Unauthorized 예외를 발생시킵니다."""
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user
```

##### [백엔드] `backend/app/llm.py` - 입력 검증 및 오케스트레이션 파이프라인
```python
class ChatRequest(BaseModel):
    """Pydantic v2 StringConstraints를 활용한 질문 본문 검증"""
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]

@router.post("/chat", dependencies=[Depends(require_csrf_header)])
async def chat(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    user_id = user.id

    # 1. 최근 대화 문맥 5쌍 조회 (동기 DB 연산을 run_in_threadpool로 스레드 풀에 위임)
    chats = await run_in_threadpool(get_recent_chats_by_user, db, user_id)

    # 2. OpenAI 규격 메시지 리스트 평탄화 (과거 순서)
    history: list[dict[str, str]] = []
    for chat in chats:
        history.extend([
            {"role": "user", "content": chat.question},
            {"role": "assistant", "content": chat.answer},
        ])

    # 3. 외부 AI 서비스 비동기 호출 및 502/504 상태 코드 변환 (에러 마스킹)
    try:
        answer = await llm_connect.generate_answer(payload.question, history=history)
    except AITimeoutError:
        raise HTTPException(status_code=504, detail="AI 응답이 지연되어 답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요.")
    except AIServiceError:
        raise HTTPException(status_code=502, detail="AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.")

    # 4. 검증된 질문·답변 한 쌍을 DB에 영구 저장 (AI 성공 시에만 원자적 저장)
    await run_in_threadpool(create_chat, db, user_id, payload.question, answer)

    return {"answer": answer}
```

##### [백엔드] `backend/app/chat_db.py` - 최신 5쌍 추출 및 오름차순 시간 복원
```python
def get_recent_chats_by_user(db: Session, user_id: int) -> list[Chat]:
    statement = (
        select(Chat)
        .where(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc(), Chat.id.desc())
        .limit(5)
    )
    chats = list(db.scalars(statement))
    # LLM이 시간 순서대로 문맥을 이해할 수 있도록 오름차순(과거 -> 최근)으로 반전
    chats.reverse()
    return chats
```

##### [백엔드] `backend/app/llm_connect.py` - AsyncOpenAI 통신 및 방어적 응답 검증
```python
# 모듈 레벨에서 클라이언트를 재사용하여 커넥션 풀 유지 (max_retries=0으로 자동 중복 질의 방지)
_client = AsyncOpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL, timeout=AI_TIMEOUT, max_retries=0)

async def generate_answer(question: str, history: list[dict[str, str]]) -> str:
    messages = [*history, {"role": "user", "content": question}]
    try:
        completion = await _client.chat.completions.create(model=AI_MODEL, messages=messages)
    except APITimeoutError:
        raise AITimeoutError("AI 응답이 제한 시간을 초과했습니다.") from None
    except (OpenAIError, JSONDecodeError):
        raise AIServiceError("AI 호출에 실패했습니다.") from None

    # 응답 유효성 방어 검증: choices 존재 여부, content 타입 및 공백 여부 검사
    ...
    return answer
```

#### 3. 핵심 동작 원리 및 보안 메커니즘
1. **CSRF 방어 (`X-Requested-With`)**: 일반적인 `<form>` 전송이나 써드파티 악성 링크로는 커스텀 HTTP 헤더를 실을 수 없다는 웹 표준 보안 특성을 이용하여 CSRF 공격을 완벽하게 차단한다.
2. **비동기 이벤트 루프 최적화 (`run_in_threadpool`)**: FastAPI의 메인 스레드 이벤트 루프가 동기식 SQLite DB I/O로 인해 멈추지 않도록 스레드 풀에 위임하여 동시성 처리 성능을 극대화한다.
3. **최근 5쌍 문맥 주입 및 정렬**: DB 인덱스를 활용해 `ORDER BY created_at DESC, id DESC LIMIT 5`로 최신 5쌍을 신속히 가져온 뒤, `chats.reverse()`로 오래된 순서로 복원하여 AI가 대화 문맥의 인과관계를 정확히 파악하도록 전달한다.
4. **민감정보 마스킹 및 502/504 에러 변환**: OpenAI 통신 에러 발생 시 외부 서비스의 API Key나 내부 시스템 스택을 노출하지 않고 `AIServiceError`(502 Bad Gateway), `AITimeoutError`(504 Gateway Timeout)로 매핑하여 안전한 한국어 에러 메시지만 응답한다.
5. **원자적 저장 원칙**: AI 응답 검증이 통과된 경우에만 `create_chat`을 호출하여, AI 오류 발생 시 쓰레기 데이터나 미완성 레코드가 DB에 남지 않도록 보장한다.

---

### 4단계: 화면의 부분 갱신 (DOM 조작)

백엔드로부터 `HTTP 200`과 함께 JSON 데이터(`{"answer": "..."}`)가 도착하면, 프론트엔드는 전체 페이지를 새로고침하지 않고 자바스크립트 DOM API를 통해 채팅창에 AI 말풍선을 동적으로 추가한다.

#### 1. 관련 파일 및 주요 심볼
- **프론트엔드 스크립트**: `backend/app/static/js/chat.js`
- **주요 함수/프로퍼티**:
  - `appendMessage(role, text)`: 말풍선 DOM 동적 생성
  - `textContent`: XSS 공격 무력화 텍스트 주입
  - `chatMessages.appendChild(bubble)`: 메시지 영역에 노드 추가
  - `scrollToBottom()`: 스크롤 자동 이동
  - `hideLoadingBubble()`: 로딩 애니메이션 제거 및 입력창 상태 복구

#### 2. 핵심 소스코드 스니펫

##### [프론트엔드] `backend/app/static/js/chat.js` - 응답 처리 및 XSS 방어 말풍선 생성
```javascript
// 1. 응답 결과 처리 분기
if (res.ok && res.data && res.data.answer) {
    // 성공: AI 답변 말풍선 추가 및 실패 캐시 초기화
    appendMessage("ai", res.data.answer);
    lastFailedQuestion = "";
} else {
    // 실패: 에러 배너 노출 및 502/504 시 원클릭 재시도 버튼 활성화
    lastFailedQuestion = question;
    ...
}

/**
 * 대화 영역에 새로운 메시지 말풍선 DOM을 생성하여 추가합니다.
 */
function appendMessage(role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}-bubble`;

    const avatar = document.createElement("div");
    avatar.className = "bubble-avatar";
    avatar.textContent = role === "user" ? "👤" : "🤖";

    const body = document.createElement("div");
    body.className = "bubble-body";

    const author = document.createElement("div");
    author.className = "bubble-author";
    author.textContent = role === "user" ? "나" : "AskMate AI";

    const content = document.createElement("div");
    content.className = "bubble-content";
    // [보안 핵심] innerHTML 대신 textContent를 사용하여 악성 스크립트 실행(XSS) 원천 차단
    content.textContent = text;

    body.appendChild(author);
    body.appendChild(content);
    bubble.appendChild(avatar);
    bubble.appendChild(body);

    messagesContainer.appendChild(bubble);
    scrollToBottom();
    return bubble;
}

/**
 * 대화 메시지 컨테이너의 스크롤을 항상 최하단으로 이동시킵니다.
 */
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
```

#### 3. 핵심 동작 원리 및 보안 메커니즘
1. **XSS (Cross-Site Scripting) 원천 방어**:
   - AI 답변이나 사용자 질문에 `<script>alert('hack')</script>`나 `<img src=x onerror=...>`와 같은 악성 HTML 태그가 포함되어 있더라도, `innerHTML`을 절대 사용하지 않고 `textContent`로 브라우저 메모리에 주입하므로 브라우저 엔진이 이를 순수 문자열(Plain Text)로만 해석하여 실행을 100% 무력화한다.
2. **동적 DOM 조작 (appendChild)**:
   - 서버에서 새로운 HTML 전체를 다시 받지 않고, `document.createElement`로 생성한 말풍선 엘리먼트만 `#chatMessages` 컨테이너의 자식으로 추가(`appendChild`)하므로 화면 깜빡임 없이 부드러운 채팅 UI를 제공한다.
3. **자동 스크롤 및 입력창 초기화**:
   - 새 메시지가 추가되면 `messagesContainer.scrollTop = messagesContainer.scrollHeight`를 호출하여 최하단으로 시야를 이동시킨다.
   - 전송 중 비활성화되었던 전송 버튼과 입력창의 잠금을 해제(`isSubmitting = false`, `disabled = false`)하고, 포커스를 입력창으로 되돌려 연속 질문이 가능하도록 한다.
4. **장애 내구성 (Fault Tolerance)과 원클릭 재시도**:
   - AI 통신 장애(502/504) 발생 시 직전 질문을 `lastFailedQuestion` 변수에 보관하고 에러 배너와 함께 [다시 시도] 버튼을 노출한다.
   - 사용자가 [다시 시도]를 누르면 질문을 다시 타이핑할 필요 없이 즉시 입력창에 복원되고 재전송된다.

---

### 5단계: 안전한 로그아웃 흐름

상단 네비게이션 바의 로그아웃 버튼을 누르면 단순 링크 이동이 아닌 비동기 API 요청을 통해 서버 세션을 안전하게 파기하고, 응답 결과에 따라 페이지 이동을 제어하는 단계이다.

#### 1. 관련 파일 및 주요 심볼
- **프론트엔드 스크립트**: `backend/app/static/js/common.js`의 `initNavbar`, `apiRequest`
- **백엔드 라우터**: `backend/app/account.py`의 `logout`
- **응답 규격**: `HTTP 204 No Content`

#### 2. 핵심 소스코드 스니펫

##### [프론트엔드] `backend/app/static/js/common.js` - 로그아웃 버튼 중복 클릭 방지 및 204 처리
```javascript
function initNavbar() {
    const logoutBtn = document.getElementById("navLogoutBtn");
    const logoutError = document.getElementById("logoutError");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            if (logoutBtn.disabled) return;
            logoutBtn.disabled = true; // 1. 중복 요청 차단을 위한 버튼 잠금
            if (logoutError) logoutError.style.display = "none";

            try {
                // 2. POST /api/logout 비동기 요청 (CSRF 헤더 자동 주입)
                const res = await apiRequest("/api/logout", {
                    method: "POST",
                    skipAuthRedirect: true, // 401 수신 시에도 핸들러 내부에서 수동 제어
                });

                // 3. 서버가 세션을 성공적으로 파기하고 204를 반환했을 때만 화면 이동
                if (res.ok && res.status === 204) {
                    window.location.assign("/login");
                    return;
                }

                // 4. 실패 시 화면 이동 없이 제자리에 머물며 에러 배너 노출
                if (logoutError) {
                    logoutError.textContent = "로그아웃에 실패했습니다. 연결 상태를 확인하고 다시 시도해 주세요.";
                    logoutError.style.display = "flex";
                }
            } finally {
                // 5. 작업 종료 후 버튼 상태 복원 (재시도 허용)
                logoutBtn.disabled = false;
            }
        });
    }
}

// apiRequest 내부의 204 파싱 예외 방어:
if (response.status === 204) {
    // 본문이 없으므로 response.json() 파싱 시 발생하는 SyntaxError를 방지하고 즉시 반환
    return { ok: true, status: 204, data: null };
}
```

##### [백엔드] `backend/app/account.py` - 세션 데이터 삭제 및 204 No Content 반환
```python
@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_header)])
def logout(request: Request) -> Response:
    """현재 브라우저에 할당된 로그인 세션을 안전하게 초기화(로그아웃)합니다.

    [기술 설명]
    1. CSRF 방지 헤더를 확인합니다.
    2. `request.session.clear()`를 호출하여 서버 측 세션 데이터를 비우고,
       응답 시 클라이언트의 쿠키를 만료시키는 Set-Cookie 헤더를 전송합니다.
    3. 이미 비로그인 상태이거나 세션이 만료된 상태에서 호출하더라도 에러 없이 멱등하게 204 No Content를 반환합니다.
    """
    logger.info("request_received path=/api/logout")
    user_id = request.session.get("user_id")
    request.session.clear()
    logger.info("logout_success user_id=%s", user_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
```

#### 3. 핵심 동작 원리 및 보안 메커니즘
1. **서버 사이드 세션 완전 파기**:
   - `request.session.clear()`를 실행하여 세션 저장소의 모든 키-값(`user_id` 등)을 즉시 삭제하고, 만료된 세션 쿠키를 클라이언트로 전송한다.
2. **HTTP 204 No Content 및 JSON 파싱 방어**:
   - 로그아웃 완료 시 본문 데이터가 필요 없으므로 HTTP 표준 상태 코드인 `204 No Content`를 반환한다.
   - 프론트엔드의 `apiRequest`는 상태 코드가 204인 경우 `response.json()` 파싱을 시도하지 않고 즉시 리턴하여 불필요한 자바스크립트 문법 에러(`SyntaxError: Unexpected end of JSON input`)를 사전에 방지한다.
3. **중복 클릭 방지 (Double-submit Prevention)**:
   - 사용자가 로그아웃 버튼을 연타하더라도 첫 클릭 시 즉시 `logoutBtn.disabled = true`가 적용되어 중복 네트워크 요청이 발생하지 않는다.
4. **엄격한 응답 검증 기반 화면 이동**:
   - 서버 응답이 명확하게 204 성공일 때만 `window.location.assign("/login")`으로 이동한다.
   - 네트워크 두절이나 서버 장애로 로그아웃 처리가 실패한 경우, 사용자를 무조건 로그인 화면으로 보내어 '로그아웃이 완료되었다'고 착각하게 만들지 않고, 에러 배너를 띄우며 버튼 잠금을 해제(`finally`)하여 즉시 재시도할 수 있도록 한다.

---

## 12. FastAPI와 데이터베이스(DB) 트랜잭션 처리 구조

AskMate는 비동기 ASGI 웹 프레임워크인 **FastAPI**와 파이썬의 표준 ORM인 **SQLAlchemy 2.0**을 결합하여, 동시 요청 환경에서도 데이터베이스 일관성(ACID)과 고성능 비동기 처리를 양립시키는 견고한 트랜잭션 파이프라인을 구축했다.

---

### 12.1 요청 단위 세션 라이프사이클 관리 (`Depends(get_db)`)

FastAPI의 의존성 주입(Dependency Injection) 시스템과 파이썬 제너레이터(컨텍스트 매니저)를 활용하여, **하나의 HTTP 요청마다 독립된 DB 세션을 할당하고 요청 처리가 완료되면 자동으로 세션을 닫아 커넥션을 반환**한다.

#### 1. 세션 제너레이터 구현 (`backend/app/db_connect.py`)
```python
def get_db() -> Generator[Session, None, None]:
    """FastAPI 경로 작동 함수(Route handler)에 주입할 요청별 독립 DB 세션을 제공합니다.

    [기술 설명]
    - FastAPI의 `Depends(get_db)`를 통해 호출되며 Python 제너레이터로 동작합니다.
    - 요청 시작 시 `SessionLocal()`로 전용 세션을 생성하고 `yield`로 전달합니다.
    - 요청 처리가 끝나면(성공 또는 에러 무관) `with` 블록 종료 시 세션을 자동으로 닫습니다(close).
    - 트랜잭션 원자성을 위해 쓰기 작업의 commit 및 rollback은 세션을 사용하는 비즈니스 로직에서 명시적으로 제어합니다.
    """
    with SessionLocal() as session:
        yield session
```

#### 2. 라우터에서의 주입 및 사용 (`backend/app/llm.py` & `backend/app/account.py`)
```python
@router.post("/chat", dependencies=[Depends(require_csrf_header)])
async def chat(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],  # HTTP 요청 라이프사이클에 바인딩된 DB 세션 주입
):
    ...
```

- **동작 원리**:
  1. 클라이언트 요청이 들어오면 FastAPI는 `get_db()` 제너레이터를 실행하여 `SessionLocal()`로부터 새로운 `Session` 객체를 생성한다.
  2. `yield session`을 통해 라우터 함수(`chat`, `signup`, `login` 등)에 세션 객체가 전달되어 사용된다.
  3. 라우터 함수의 응답이 반환되거나 도중에 예외(`HTTPException` 등)가 발생하여 요청이 종료되면, `get_db()`의 `with SessionLocal() as session:` 블록을 빠져나오며 `session.close()`가 100% 호출된다.
  4. 이를 통해 커넥션 누수(Connection Leak)가 발생하지 않으며, 요청 간의 상태 오염이 원천 차단된다.

---

### 12.2 비동기 이벤트 루프와 동기 DB 트랜잭션의 격리 (`run_in_threadpool`)

FastAPI는 기본적으로 단일 스레드 기반의 비동기 이벤트 루프(Event Loop)에서 실행된다. 반면 SQLAlchemy의 SQLite 드라이버는 동기식 파일 I/O로 동작한다.

만약 비동기 라우터(`async def`) 내부에서 동기 DB 쿼리를 직접 실행하면, 디스크 I/O 대기 시간 동안 이벤트 루프가 멈추어(Blocking) 다른 모든 사용자의 요청 처리가 지연된다.

AskMate는 이를 방지하기 위해 **Starlette의 `run_in_threadpool`을 사용하여 동기 DB 트랜잭션을 별도의 워커 스레드 풀로 격리**한다.

#### 비동기 스레드 풀 격리 코드 (`backend/app/llm.py`)
```python
# 1단계: 최근 대화 문맥 조회 (동기 DB 읽기를 스레드 풀에 위임)
try:
    chats = await run_in_threadpool(get_recent_chats_by_user, db, user_id)
except SQLAlchemyError:
    logger.exception("db_read_failure operation=chat_context user_id=%s", user_id)
    raise HTTPException(status_code=500, detail="최근 대화 기록을 불러오지 못했습니다.") from None

# ... 비동기 외부 AI API 통신 (이벤트 루프 활용) ...

# 4단계: 정상 답변 수신 완료 시 질문·답변 한 쌍을 DB에 저장 (동기 DB 쓰기를 스레드 풀에 위임)
try:
    chat_id = await run_in_threadpool(create_chat, db, user_id, payload.question, answer)
except SQLAlchemyError:
    logger.exception("db_save_failure operation=chat user_id=%s", user_id)
    raise HTTPException(status_code=500, detail="대화 기록을 저장하지 못했습니다.") from None
```

- **기술적 이점**:
  - 무거운 DB 파일 읽기/쓰기가 진행되는 동안에도 FastAPI 메인 이벤트 루프는 쉬지 않고 다른 클라이언트의 로그인, 정적 파일 서빙, 헬스체크(`/health`)를 논블로킹으로 동시 처리할 수 있다.

---

### 12.3 데이터 접근 계층(DAL)의 원자적 트랜잭션 제어 (Commit & Rollback)

데이터의 일관성과 원자성(Atomicity)을 보장하기 위해, 모든 쓰기(INSERT/UPDATE/DELETE) 트랜잭션은 **`flush()` ➔ `commit()` ➔ 실패 시 `rollback()`** 패턴으로 구현되었다.

#### 1. 대화 기록 트랜잭션 (`backend/app/chat_db.py`)
```python
def create_chat(db: Session, user_id: int, question: str, answer: str) -> int:
    """질문과 AI 답변 한 쌍을 데이터베이스에 영구 저장하고 생성된 기록 ID를 반환합니다."""
    chat = Chat(user_id=user_id, question=question, answer=answer)
    db.add(chat)
    try:
        db.flush()      # 1. DB에 쿼리를 전송하여 기본키(chat.id)를 채번/확보
        chat_id = chat.id
        db.commit()     # 2. 트랜잭션을 디스크에 영구 반영
    except SQLAlchemyError:
        db.rollback()   # 3. 예외 발생 시 보류 중인 모든 변경사항을 취소하고 세션을 복원
        raise           # 4. 상위 라우터가 500 에러 처리 및 로깅을 할 수 있도록 재전파
    return chat_id
```

#### 2. 사용자 계정 생성 트랜잭션 (`backend/app/account_db.py`)
```python
def create_user(db: Session, username: str, password_hash: str) -> int:
    """신규 사용자를 데이터베이스에 저장하고 발급된 고유 사용자 ID를 반환합니다."""
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    try:
        db.flush()      # UNIQUE 제약조건 검사 실행 및 user.id 확보
        user_id = user.id
        db.commit()     # 최종 커밋
    except SQLAlchemyError:
        db.rollback()   # 고유 제약조건 위반(중복 아이디) 시 롤백하여 세션 정상화
        raise
    return user_id
```

- **핵심 메커니즘**:
  1. **`db.flush()`의 활용**: 트랜잭션을 최종 커밋하기 전, 데이터베이스 엔진에 INSERT 쿼리를 실행시켜 데이터베이스가 자동 생성한 Auto-increment 기본키(`id`)를 즉시 획득한다.
  2. **원자적 실패 복구 (`db.rollback()`)**: 동시 가입으로 인한 고유 제약조건 위반(`IntegrityError`)이나 디스크 입출력 에러 발생 시 즉각 롤백을 수행하여 세션 내에 깨진 변경사항이 잔류하지 않도록 세션을 깨끗한 상태로 되돌린다.
  3. **AI 통신 실패 시 미저장 원칙**: AI 모델 호출이 완료되어 100% 온전한 응답을 획득했을 때만 `create_chat`을 호출하므로, AI 오류 시 반쪽짜리 쓰레기 대화 데이터가 DB에 남는 일이 구조적으로 불가능하다.

---

### 12.4 멀티스레드 환경 및 보안을 위한 엔진 설정 (`backend/app/db_connect.py`)

SQLite 엔진 인스턴스를 생성할 때 멀티스레드 동시성과 데이터 무결성, 보안을 보장하는 특수 옵션들을 구성했다.

```python
engine = create_engine(
    URL.create("sqlite", database=str(DATABASE_PATH)),
    connect_args={"check_same_thread": False},  # 1. 멀티스레드 세션 공유 지원
    hide_parameters=True,                       # 2. 쿼리 파라미터(비밀번호 등) 로그 마스킹
)

@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, connection_record):
    """새로운 SQLite DB 커넥션이 열릴 때마다 외래키 제약조건 검사를 활성화합니다."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")    # 3. 외래키 참조 무결성 강제
    cursor.close()
```

1. **`check_same_thread=False`**:
   - SQLite의 기본 동작은 커넥션을 생성한 단일 스레드에서만 사용하도록 제한한다.
   - FastAPI는 요청 처리 중 비동기 이벤트 루프와 워커 스레드 풀(`run_in_threadpool`)을 오가므로, 이 옵션을 `False`로 지정해야 스레드 전환 시 `ProgrammingError`가 발생하지 않는다.
2. **`hide_parameters=True`**:
   - DB 에러 발생 시 예외 객체나 로그에 바인딩된 파라미터 값(사용자 비밀번호 해시, 개인 질문 내용 등)이 평문으로 남지 않도록 자동으로 마스킹(`[SQL: ...] [parameters: [redacted]]`)한다.
3. **`PRAGMA foreign_keys=ON`**:
   - SQLite는 하위 호환성을 이유로 기본적으로 외래키(FK) 검사를 수행하지 않는다.
   - 커넥션 풀에서 새 연결이 초기화될 때마다 이벤트 리스너를 통해 외래키를 활성화하여, `chats.user_id`가 존재하지 않는 유저를 참조하는 데이터 고아 현상을 차단한다.

---

### 12.5 전체 DB 트랜잭션 라이프사이클 흐름도

```text
[클라이언트 요청] ──→ POST /api/chat
         │
         ▼
[FastAPI 의존성 주입]
 ├── get_db() 제너레이터 실행
 │     └── session = SessionLocal() (새 세션 오픈)
 ├── get_current_user (세션 기반 유저 인증)
 └── require_csrf_header (CSRF 헤더 검증)
         │
         ▼
[1. 문맥 조회 트랜잭션]
 └── run_in_threadpool(get_recent_chats_by_user, db, user_id)
       ├── 워커 스레드로 전환
       ├── SELECT * FROM chats WHERE user_id = ? ORDER BY ... LIMIT 5
       └── 결과 리스트 반환 (읽기 전용, 락 해제)
         │
         ▼
[2. 외부 AI 통신 (Non-blocking I/O)]
 └── await llm_connect.generate_answer(...)
       └── 외부 API 대기 중 (DB 세션은 유휴 상태 유지)
         │
   ┌─────┴─────────────────────────┐
   │ [AI 통신 실패 (502/504)]       │ [AI 통신 성공 (200)]
   ▼                               ▼
[DB 저장 생략]            [3. 저장 트랜잭션 실행]
(미저장 원칙 적용)         └── run_in_threadpool(create_chat, db, user_id, ...)
                                  ├── db.add(chat)
                                  ├── db.flush() (INSERT 실행 및 PK 추출)
                                  ├── db.commit() (영구 커밋)
                                  └── 예외 발생 시 db.rollback()
         │                                 │
         └────────────────┬────────────────┘
                          ▼
[요청 종료 및 세션 반환]
 └── get_db()의 with 블록 종료 ➔ session.close() (커넥션 풀 반환)
         │
         ▼
[클라이언트에 JSON 응답 반환]
```

---

## 13. 핵심 요약

- **배포 주소 접속 (`http://134.185.97.62/`)**:
  - 기본 HTTP 포트인 80번 포트로 OCI 호스트에 접근하여 Docker 포트포워딩을 통해 컨테이너 내부 Uvicorn(8000)으로 전달된다.
  - 최초 루트 요청(`GET /`)은 서버의 `307 Temporary Redirect`에 의해 `/login`으로 자동 이동된다.
  - 비로그인 상태는 `login.html`이 렌더링되고, 이미 로그인된 상태는 `303 See Other`에 의해 `/chat`으로 자동 직행한다.
- **HTML, CSS, JS 분업**:
  - HTML은 최초 화면의 구조를 만들고, CSS는 화면의 모양을 꾸민다.
  - JavaScript는 사용자의 행동과 서버 API를 비동기로 연결하여 화면의 일부분만 동적으로 바꾼다.
- **안전한 한글 입력**:
  - 한글 자모 조합 중(IME `isComposing`) 누르는 Enter는 질문 전송을 차단하여 글자 중복과 오작동을 방지한다.
- **FastAPI & DB 트랜잭션**:
  - `get_db` 제너레이터로 요청 단위 세션 자동 할당 및 `close()` 반환.
  - `run_in_threadpool`을 통해 동기 DB 작업을 워커 스레드로 격리하여 비동기 이벤트 루프 블로킹 방지.
  - `flush()` ➔ `commit()` ➔ 실패 시 `rollback()` 원자적 트랜잭션과 AI 성공 시에만 저장하는 미저장 원칙 준수.
- **로그아웃 안전성**:
  - 로그아웃은 서버 응답이 204 성공일 때만 페이지를 이동하며, 실패 시 에러 안내와 재시도를 지원한다.



