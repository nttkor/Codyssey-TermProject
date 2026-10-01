# 프론트엔드와 백엔드 통신 흐름

이 문서는 AskMate 프로젝트를 예시로, 브라우저에서 `/chat`에 접속한 뒤 질문을 전송하고 AI 답변을 화면에 표시하기까지의 과정을 쉽게 설명한다.

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

## 3. `/chat`에 처음 접속했을 때

웹 주소는 `~/chat`이 아니라 `/chat`이다. `~`는 터미널에서 사용자의 홈 디렉터리를 뜻한다.

브라우저에서 다음 주소를 연다고 가정한다.

```text
http://127.0.0.1:8000/chat
```

### 3.1 브라우저가 HTML 화면을 요청한다

```text
브라우저 → GET /chat → FastAPI 서버
```

브라우저는 세션 쿠키가 있다면 요청과 함께 전송한다.

```http
GET /chat
Cookie: askmate_session=...
```

### 3.2 서버가 로그인 여부를 확인한다

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

### 3.3 브라우저가 CSS와 JavaScript를 요청한다

브라우저는 받은 HTML을 분석한다. HTML 안에서 CSS와 JavaScript 파일 참조를 발견하면 해당 파일을 서버에 추가로 요청한다.

```text
chat.html  → 입력창, 전송 버튼, 채팅 영역 생성
style.css  → 채팅 화면의 디자인 적용
common.js  → 공통 API 요청과 로그아웃 기능 준비
chat.js    → 질문 전송과 답변 표시 기능 준비
```

### 3.4 JavaScript가 이벤트를 연결한다

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

## 4. 사용자가 질문을 전송했을 때

### 4.1 전송 버튼과 Enter 키 입력 (`submit` 이벤트)

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

### 4.2 일반적인 HTML 폼 제출을 중단한다

일반적인 HTML 폼은 제출되면 새로운 페이지로 이동한다. 현재 프로젝트에서는 JavaScript가 이 기본 동작을 막는다.

```javascript
form.addEventListener("submit", async (event) => {
    event.preventDefault();
});
```

`event.preventDefault()` 때문에 현재 `/chat` 페이지가 다른 페이지로 바뀌지 않는다.

### 4.3 JavaScript가 현재 화면에 질문을 표시한다

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

## 5. JavaScript가 백엔드 API를 호출한다

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

## 6. 백엔드가 질문을 처리한다

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

## 7. `response`와 화면 변경의 관계

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

## 8. 페이지 전체를 새로고침하지 않는 원리

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

## 9. 전체 통신 흐름

### 9-1. 질문 및 답변 통신 흐름

```text
브라우저에서 /chat 접속
        ↓
GET /chat 요청과 세션 쿠키 전송
        ↓
FastAPI가 로그인 사용자 확인
        ↓
비로그인 ───────────────→ /login으로 이동
        ↓ 로그인 상태
Jinja2로 chat.html 생성 및 반환
        ↓
브라우저가 CSS와 JavaScript 추가 요청
        ↓
화면 표시 및 JavaScript 이벤트 연결 (IME 조합 및 Enter 처리)
        ↓
사용자가 질문 입력 후 전송
        ↓
event.preventDefault()로 페이지 이동 방지
        ↓
JavaScript가 POST /api/chat 요청
        ↓
FastAPI가 최근 대화 5쌍 조회
        ↓
외부 AI 서비스 호출 및 안전한 응답 검증
        ↓
정상 답변 시 SQLite에 저장 (실패 시 미저장 & 502/504)
        ↓
JSON 응답 반환
        ↓
JavaScript가 JSON에서 답변 추출
        ↓
현재 채팅 화면에 답변 말풍선 추가 (오류 시 재시도 버튼 표시)
```

### 9-2. 로그아웃 통신 흐름과 안정성 보장 (`POST /api/logout`)

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

## 10. 핵심 요약

- HTML은 최초 화면의 구조를 만든다.
- CSS는 화면의 모양을 꾸민다.
- JavaScript는 사용자의 행동과 서버 API를 연결한다.
- `/chat`은 채팅 HTML 화면을 제공한다.
- `/api/chat`은 질문을 받아 AI 답변 데이터를 반환한다.
- 한글 조합 중(IME `isComposing`) 누르는 Enter는 질문 전송을 차단하여 한글 중복 입력을 방지한다.
- `response`는 함수가 아니라 HTTP 응답 객체다.
- JavaScript가 응답에서 데이터를 꺼내 DOM을 변경한다.
- `event.preventDefault()`와 `fetch()`를 사용하기 때문에 페이지 전체를 새로고침하지 않아도 된다.
- AI 실패 시 데이터베이스에 질문과 답변을 저장하지 않는다.
- 로그아웃은 서버 응답이 204 성공일 때만 페이지를 이동하며, 실패 시 에러 안내와 재시도를 지원한다.

