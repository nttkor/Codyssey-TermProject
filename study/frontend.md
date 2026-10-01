# AskMate 프론트엔드 공부 노트

**기준:** `fix/qa-findings` / `baa13d5` (PR #36 반영 완료). 코드 경로는 `backend/` 기준입니다. 전체 호출 순서는 [flow.md](flow.md)를 함께 읽어 주세요.

## 1. 프론트엔드가 맡는 일

프론트엔드는 사용자가 직접 보는 화면과 그 화면에서 일어나는 상호작용을 담당합니다. 이 프로젝트에서는 HTML·CSS·JavaScript와 서버 측 Jinja2 템플릿을 사용합니다. 별도의 React 앱이나 프론트 개발 서버는 없습니다.

| 기술 | 쉬운 설명 | 프로젝트 예시 |
| --- | --- | --- |
| HTML | 화면에 어떤 요소가 있는지 정의합니다. | 폼, 입력창, 버튼, 말풍선 영역 |
| CSS | 요소를 어떻게 배치하고 보여줄지 정합니다. | 카드, 색상, 모바일 레이아웃 |
| JavaScript | 사용자의 행동에 반응하고 데이터를 가져옵니다. | 질문 전송, 기록 조회, 오류 표시 |
| Jinja2 | 서버가 데이터를 HTML에 넣어 완성합니다. | 로그인 사용자 이름, 공통 메뉴 |

중요한 구분은 **서버가 HTML을 만드는 시점**과 **브라우저가 JS로 화면을 바꾸는 시점**입니다. `{{ user.username }}`은 서버에서 처리되고, `appendMessage()`는 브라우저에서 실행됩니다.

## 2. 파일 지도

| 파일 | 역할 | 볼 곳 |
| --- | --- | --- |
| `app/templates/base.html` | 공통 머리말·메뉴·본문·푸터, CSS·JS 로드 | `7~9`, `19~41` |
| `app/templates/signup.html` | 회원가입 폼 | `13~73`, 전용 JS `82~84` |
| `app/templates/login.html` | 로그인 폼 | `13~54`, 전용 JS `63~65` |
| `app/templates/chat.html` | 메시지·오류·입력 영역 | `21~61`, 전용 JS `67~69` |
| `app/templates/history.html` | 로딩·빈 목록·오류·기록 영역 | `20~46`, 전용 JS `50~52` |
| `app/static/js/common.js` | API 요청, 오류 메시지, 토글, 로그아웃 | `apiRequest()`, `getErrorMessage()`, `initPasswordToggles()`, `initNavbar()` |
| `app/static/js/signup.js` | 가입 검증·전송·이동 | `checkPasswordMatch()`, submit 핸들러 |
| `app/static/js/login.js` | 로그인·가입 완료 안내 | 초기화, submit 핸들러 |
| `app/static/js/chat.js` | 입력·전송·말풍선·로딩·재시도 | `updateCharCounter()`, `appendMessage()`, submit 핸들러 |
| `app/static/js/history.js` | 기록 요청·카드 렌더링 | `fetchHistory()` |
| `app/static/css/style.css` | 공통 스타일과 반응형 구성 | `:root`, 각 화면 선택자, `@media` |

`app/static/js/main.js`의 `signupUser():2~22`는 가입 API 호출 예시입니다. 현재 화면 템플릿은 이 파일을 로드하지 않으므로 실제 가입 동작은 `signup.js`에서 읽어야 합니다.

## 3. Jinja2 템플릿 상속

확인 위치: `templates/base.html:6~9,41`, 각 화면의 `extends`·`block` 부분입니다.

```text
base.html
  ├─ title 블록 ← 화면별 제목
  ├─ scripts 블록 ← 화면별 JavaScript
  ├─ 공통 헤더·메뉴
  ├─ content 블록 ← 화면별 본문
  └─ 공통 푸터
```

`{% extends "base.html" %}`은 공통 틀을 사용한다는 뜻이고, `{% block content %}`는 틀의 특정 부분을 채운다는 뜻입니다. 모든 화면에 같은 메뉴를 복사할 필요가 없습니다.

`url_for('chat_page')`는 함수 이름에 연결된 경로를 만듭니다. `url_for('static', path='/js/chat.js')`는 정적 파일 URL을 만듭니다. `pages.py`의 함수 이름과 `main.py`의 정적 파일 마운트를 함께 보면 연결이 보입니다.

`base.html:19~32`는 `user`가 있으면 채팅·기록·로그아웃 메뉴를 보여 줍니다. 하지만 **메뉴를 숨기는 것은 보안 검사가 아닙니다.** 사용자는 URL과 API를 직접 호출할 수 있으므로 서버의 `auth.py`, `pages.py`가 실제 접근을 막아야 합니다.

## 4. DOM과 이벤트를 이해해 주세요

DOM은 브라우저가 HTML을 읽어 만든 요소들의 객체 구조입니다. JS는 이 객체를 찾아 값을 읽거나 화면을 바꿉니다.

```text
HTML: <textarea id="chatInput">...</textarea>
  → document.getElementById("chatInput")
  → 객체의 value를 읽기
  → disabled / style / textContent 변경
```

`addEventListener("submit", handler)`는 제출 행동이 발생할 때 실행할 함수를 등록합니다. JS 파일을 읽자마자 API를 호출하는 것과 다릅니다. 이름이 없는 `async (e) => { ... }`도 함수이며, 이 노트에서는 “submit 핸들러”처럼 이벤트 이름과 라인으로 찾을 수 있게 표시합니다.

공통 JS와 화면별 JS는 `defer`로 로드하며 `DOMContentLoaded`에서 요소를 찾고 이벤트를 등록합니다. `if (!form) return`은 해당 화면에 폼이 없으면 초기화를 중단하는 방어 코드입니다.

`e.preventDefault()`는 폼의 기본 페이지 이동을 막습니다. 대신 JS가 JSON API를 호출하므로 현재 화면에서 로딩·오류·결과를 제어할 수 있습니다.

## 5. 공통 API 클라이언트

핵심 위치는 `static/js/common.js:7~61`, `apiRequest()`입니다.

### 5.1 객체와 JSON은 다릅니다

화면에서 만든 `{ question: "설명해 주세요" }`는 JS 객체입니다. HTTP 본문에 보내려면 `JSON.stringify()`로 JSON 문자열로 바꿉니다. 응답은 `response.json()`으로 다시 JS 데이터로 읽습니다.

`Content-Type: application/json`은 본문을 어떤 형식으로 해석할지 알려 줍니다. `X-Requested-With: XMLHttpRequest`는 이 프로젝트의 POST 헤더 검사에 맞추는 값입니다. `fetch()`를 쓰더라도 헤더 문자열은 이 이름을 사용하며, 실제 XMLHttpRequest 객체를 만드는 것은 아닙니다.

### 5.2 같은 출처와 쿠키

출처는 프로토콜·호스트·포트의 조합입니다. `http://127.0.0.1:8000/chat`와 `http://127.0.0.1:8000/api/chat`은 같은 출처입니다. 포트가 달라지면 다른 출처입니다.

현재 코드는 상대 URL인 `/api/chat` 등을 사용합니다. 기본 `fetch()`의 같은 출처 쿠키 전송 동작으로 로그인 쿠키가 함께 갑니다. JS에서 쿠키를 읽어 `Authorization` 헤더를 만들지 않습니다.

### 5.3 결과 객체

```javascript
{ ok: true, status: 200, data: { answer: "응답" } }
{ ok: false, status: 502, data: { detail: "안내" } }
{ ok: true, status: 204, data: null }
```

- `ok`는 HTTP 성공 여부입니다.
- `status`는 HTTP 코드이며, 프론트 내부 실패는 0으로 표현합니다.
- `data`는 JSON으로 읽은 데이터입니다.

HTTP 4xx·5xx 응답은 보통 `fetch()`를 예외로 만들지 않습니다. 네트워크 실패나 JSON 파싱 실패는 `catch`로 갑니다. 따라서 `try/catch`만 있고 `response.ok` 확인이 없으면 서버 오류를 놓칠 수 있습니다.

204 응답은 본문이 없으므로 JSON 파싱하지 않습니다(`common.js:38~41`). `getErrorMessage():64~71`는 문자열 `detail`과 검증 오류 배열 `detail`을 모두 화면 문구로 변환합니다.

## 6. 회원가입 화면

확인 위치: `signup.js:18~36`, `checkPasswordMatch()`와 `38~107`의 submit 핸들러입니다.

1. 입력 이벤트마다 비밀번호 확인 문구를 갱신합니다.
2. 제출할 때 사용자명 앞뒤 공백을 제거하고 소문자로 바꿉니다.
3. 사용자명은 영문·숫자·밑줄 3~30자로 검사합니다.
4. 비밀번호는 8~128자로 검사하고 확인 값과 비교합니다.
5. 제출 버튼을 잠그고 `{username, password}`만 전송합니다.
6. 201이면 잠시 성공 안내를 보인 뒤 `/login?registered=1`로 이동합니다.
7. 409이면 중복 사용자명 안내, 다른 오류는 공통 메시지를 표시합니다.

비밀번호에 `trim()`을 적용하지 않습니다. 사용자가 실제로 정한 공백도 비밀번호의 일부일 수 있기 때문입니다. 비밀번호 확인은 서버에 보내지 않습니다.

`signup.html:13`의 `novalidate`는 브라우저 기본 폼 검증을 끄고 JS 검증으로 안내하도록 합니다. 다만 프론트 검증은 우회 가능하므로 서버가 같은 핵심 조건을 다시 검사합니다.

## 7. 로그인 화면

확인 위치: `login.js:15~21,23~62`입니다.

가입 완료 여부는 `URLSearchParams`로 `registered=1`을 읽어 표시합니다. 이 값은 **안내용 표시**이며 로그인이나 실제 가입 성공을 보증하지 않습니다. 주소에 직접 넣을 수도 있습니다.

로그인 요청에는 `skipAuthRedirect: true`를 넣습니다. 로그인 API의 401은 “아직 로그인 안 됨”뿐 아니라 “아이디나 비밀번호가 틀림”을 뜻하기 때문입니다. 공통 함수가 고정 문구로 바꾸지 않고 서버의 실제 안내를 보여 주게 합니다.

성공하면 `/chat`으로 이동합니다. 실패하면 버튼을 복구하고 비밀번호 입력칸을 비운 뒤 다시 포커스합니다. 사용자명은 서버에서도 정규화되며, 비밀번호는 원본 그대로 전달합니다.

## 8. 채팅 화면: 상태를 분리해서 읽어 주세요

확인 위치: `chat.js:19~21`입니다.

| 상태 | 의미 | 적용 범위 |
| --- | --- | --- |
| `isSubmitting` | 현재 이 화면에서 요청을 기다리는지 | 중복 제출 차단 |
| `isComposing` | 한글 등의 글자를 조합 중인지 | Enter 오작동 방지 |
| `lastFailedQuestion` | 마지막 실패 질문 | 재시도 복원 |

이 변수들은 페이지 JS 메모리에 있습니다. 새로고침하면 초기화되며 DB에 저장되지 않습니다. 다른 탭의 제출을 막지도 않습니다.

### 8.1 입력 검증·글자 수·높이

`updateCharCounter():29~45`는 입력값 길이와 공백 제거 결과를 보고 버튼을 활성화합니다. 입력창 높이는 `scrollHeight`를 이용하여 최대 160px까지 늘립니다. `chat.html:52`의 `maxlength="1000"`도 입력을 제한합니다.

JS의 문자열 `length`는 UTF-16 코드 단위 수이고 Python의 일반 문자열 길이는 유니코드 코드 포인트 수입니다. 일부 유니코드 문자는 두 환경에서 길이가 다를 수 있습니다. 화면과 서버가 항상 같은 “눈에 보이는 글자 수”를 세는 것은 아니며, 서버 검증이 최종 기준입니다.

### 8.2 Enter와 입력기 조합

`chat.js:55~69`를 보세요. 한글 입력기는 자음·모음을 조합하면서 이벤트를 보냅니다. 조합 확정 Enter를 제출로 처리하면 아직 입력 중인 질문이 전송될 수 있습니다.

- `compositionstart`: 조합 중으로 표시합니다.
- `compositionend`: 조합 종료로 표시합니다.
- `keydown`: 조합 상태, `e.isComposing`, 호환용 `keyCode === 229`를 확인합니다.
- 일반 Enter는 제출하고 Shift+Enter는 줄바꿈을 유지합니다.

`form.dispatchEvent(new Event("submit", {cancelable: true}))`는 버튼 클릭과 비슷한 제출 경로로 연결하지만 합성 이벤트입니다. 현재 검증 로직은 submit 핸들러 안에서도 실행됩니다.

### 8.3 요청 대기와 결과 처리

`chat.js:166~227`에서 다음 상태 전환을 읽어 주세요.

```text
입력 가능
  → 요청 중: 버튼·입력 잠금, 질문 말풍선, 로딩 표시
       ├─ 성공: AI 말풍선
       └─ 실패: 오류 배너, 필요 시 재시도
  → 로딩 제거, 입력 잠금 해제
```

`appendMessage():102~129`는 화면 DOM만 만듭니다. `showLoadingBubble():132~158`와 `hideLoadingBubble():160~163`은 응답 대기를 시각적으로 표시합니다. 점이 움직여도 서버가 스트리밍하는 것은 아닙니다. 현재 API는 전체 답변을 한 번에 반환합니다.

### 8.4 재시도

502·504에서만 재시도 버튼을 보여 줍니다(`205~216`). 클릭하면 `lastFailedQuestion`을 입력창에 넣고 submit 이벤트를 다시 보냅니다(`90~99`). 질문 말풍선도 다시 추가되므로 화면에 같은 질문이 반복될 수 있습니다.

이 코드는 AI SDK의 자동 재시도와 별개입니다. SDK는 자동 재시도를 끄고, 사용자가 화면에서 새 요청을 결정합니다.

## 9. 기록 화면

확인 위치: `history.js:19~115`, `fetchHistory()`입니다.

기록 화면은 로딩·오류·빈 기록·정상 목록을 구분합니다. 요청 전에 기존 표시를 숨기고 응답에 맞는 상태를 보여 줍니다. 실패 후 다시 불러오기와 정상 목록의 새로고침 모두 같은 함수를 사용합니다.

서버가 이미 최신순으로 반환하므로 JS는 받은 순서대로 카드들을 만듭니다. `new Date(item.created_at).toLocaleString("ko-KR", ...)`는 한국어 형식으로 표시하지만 시간대는 브라우저의 로컬 시간대입니다. 한국어 형식이라고 항상 한국 표준시가 되는 것은 아닙니다.

각 카드의 `#번호`는 화면상의 순서 번호입니다(`71~72`). 실제 DB 식별자가 아니므로 디버깅할 때는 API 응답의 `id`를 확인해야 합니다.

현재 `fetchHistory()`는 요청 중복 잠금이나 최신 응답 식별 기능이 없습니다. 여러 번 누르면 요청이 겹칠 수 있다는 점은 채팅의 `isSubmitting`과 구분해 주세요.

## 10. 로그아웃·비밀번호 토글

### 로그아웃

`common.js:89~115`, `initNavbar()`를 보세요.

- 처리 중 버튼을 잠가 같은 화면의 중복 클릭을 막습니다.
- 공통 401 리다이렉트를 건너뛰고 결과를 직접 확인합니다.
- **204 성공일 때만** 로그인 화면으로 이동합니다.
- 실패하면 공통 메뉴 아래에 안내를 표시하고 화면을 유지합니다.
- `finally`에서 버튼을 복구하므로 다시 시도할 수 있습니다.

이동을 성공처럼 처리하는 것과 서버가 실제 로그아웃을 수행한 것은 다릅니다. 네트워크 실패에는 결과를 단정하지 않고 실패 안내를 보여 줍니다.

### 비밀번호 표시·숨김

`common.js:74~86`, `initPasswordToggles()`는 `data-target`로 대상 입력을 찾아 `type`만 바꿉니다. 값이나 해시는 바꾸지 않습니다. `type="password"`는 화면에서 가리는 기능일 뿐 전송 암호화가 아닙니다. 안전한 전송에는 HTTPS가 필요합니다.

## 11. XSS 방지: 글자를 HTML로 해석하지 않기

XSS는 공격자가 넣은 내용이 브라우저에서 실행 가능한 코드로 해석되는 문제입니다. 질문이나 AI 답변도 외부 입력이므로 믿고 HTML로 넣으면 안 됩니다.

```javascript
content.textContent = text;
```

`textContent`는 내용이 HTML처럼 생겨도 글자로 표시합니다. 현재 질문·답변은 `chat.js:117~119`, `history.js:85~87,100~102`에서 이 방식을 사용합니다. 따라서 AI가 Markdown을 반환해도 현재 화면은 별도 Markdown 렌더링을 하지 않습니다.

`innerHTML`을 쓰는 곳도 있습니다. 로딩 점의 고정 문자열(`chat.js:149`)과 목록 비우기(`history.js:48`)는 사용자 내용을 HTML에 섞는 코드와 다릅니다. **위험은 메서드 이름만이 아니라 어떤 데이터를 넣는가에 달려 있습니다.**

서버 템플릿의 일반 HTML 값은 Jinja2의 이스케이프 동작을 사용합니다. `safe`로 신뢰하지 않는 값을 강제로 풀어 주면 위험해질 수 있으므로 별도 보안 검토가 필요합니다.

## 12. CSS·반응형·접근성

| 코드 위치 | 공부할 개념 |
| --- | --- |
| `style.css:1`부터 `:root` | CSS 변수로 공통 색상·간격 등을 관리합니다. |
| `style.css:66~150` | 공통 버튼, disabled와 hover 상태를 구분합니다. |
| `style.css:152~181` | 성공·오류·주의 알림 스타일을 구분합니다. |
| `style.css:295~406` | 계정 폼·카드 레이아웃을 구성합니다. |
| `style.css:408~708` | 채팅 영역, 말풍선, 입력창을 구성합니다. |
| `style.css:598~620` | 로딩 점의 CSS 애니메이션을 구성합니다. |
| `style.css:710~856` | 기록 카드·로딩 표시를 구성합니다. |
| `style.css:837~847` | `white-space: pre-wrap`으로 기록의 줄바꿈을 유지합니다. |
| `style.css:858~901` | 화면 폭 640px 이하에서 레이아웃을 변경합니다. |

반응형은 작은 화면에서도 같은 내용을 사용할 수 있게 배치를 바꾸는 것입니다. 별도 모바일 HTML을 만드는 것은 아닙니다.

`chat.html:21`의 `role="log"`, `aria-live="polite"`는 새 메시지를 보조 기술에 알리는 데 도움을 줍니다. 오류의 `role="alert"`, 버튼의 `aria-label`, 입력의 `<label for="...">`도 접근성을 위한 요소입니다. 이런 속성이 있다고 전체 접근성이 검증된 것은 아닙니다.

## 13. 직접 확인하는 방법

브라우저 개발자 도구에서 다음을 관찰해 주세요. 실제 서비스 실행에는 환경 설정과 AI 비용이 필요할 수 있으며, 이번 노트 작성 중 실행하지 않았습니다.

1. Network에서 `/chat`의 HTML 요청과 `/api/chat`의 JSON 요청을 구분해 주세요.
2. 가입 요청 본문에 비밀번호 확인 필드가 없는지 확인해 주세요.
3. 로그인 응답의 `Set-Cookie`와 이후 요청의 쿠키를 확인해 주세요. 값은 복사·공유하지 마세요.
4. 채팅에서 로딩 중 입력창과 버튼이 비활성화되는지 확인해 주세요.
5. 기록의 `created_at` 원본과 화면에 표시한 시각을 비교해 주세요.
6. 새로고침 후 말풍선은 초기화되어도 기록 API에는 저장 내용이 남는지 구분해 주세요.

입력기 회귀 테스트는 `tests/frontend/chat-input.test.cjs`, 로그아웃 테스트는 `tests/frontend/logout.test.cjs`에 있습니다. 가짜 DOM·이벤트 테스트이므로 실제 OS 한글 입력기와 CSS 레이아웃까지 검증하는 것은 아닙니다.

## 14. 설명 연습과 참고 개념

- 프론트 검증을 우회할 수 있는 이유와 서버 검증의 필요성을 설명해 주세요.
- HTTP 500과 `fetch()` 네트워크 실패를 코드에서 어떻게 구분하나요?
- 로그인 쿠키를 JS가 읽지 않아도 인증 요청이 가능한 이유는 무엇인가요?
- 한글 조합 Enter를 일반 Enter와 구분하는 이유는 무엇인가요?
- 로딩 점, AI 스트리밍, DB 저장 상태는 각각 무엇이 다른가요?
- `textContent`와 `innerHTML`을 언제 구분해야 하나요?

추가 학습 링크:

- [MDN DOM 소개](https://developer.mozilla.org/ko/docs/Web/API/Document_Object_Model/Introduction)
- [MDN Fetch API](https://developer.mozilla.org/ko/docs/Web/API/Fetch_API)
- [MDN 이벤트](https://developer.mozilla.org/ko/docs/Learn_web_development/Core/Scripting/Events)
- [Jinja 템플릿 상속](https://jinja.palletsprojects.com/en/stable/templates/#template-inheritance)
