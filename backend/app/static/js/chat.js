/**
 * AskMate 실시간 AI 채팅 화면 전용 클라이언트 스크립트 (chat.js)
 *
 * [파일 개요]
 * 본 모듈은 AskMate AI 대화 화면(`/chat`)의 사용자 인터페이스 전반을 제어합니다.
 * 실시간 글자수 계산 및 1000자 초과 방지, 동적 텍스트 영역 높이 조절,
 * 한글 조합(IME) 중복 전송 방지 키보드 이벤트 핸들러, 대화 말풍선 안전 렌더링(XSS 원천 차단),
 * AI 응답 대기 로딩 인디케이터(Typing dots), 그리고 502/504 장애 시의 원클릭 재시도 매커니즘을 구현합니다.
 *
 * [핵심 기술적 설명]
 * 1. 한글 IME 조합 중복 전송 완벽 방어:
 *    - 한글/일본어 등 CJK 문자는 여러 자모가 결합되는 조합(Composition) 과정을 거칩니다.
 *    - 글자 조합 중 Enter 키를 누르면 브라우저에 따라 조합 확정용 Enter 이벤트가 발생하여
 *      메시지가 의도치 않게 전송되는 버그가 자주 발생합니다.
 *    - `isComposing`, `e.isComposing`, 그리고 일부 브라우저(Safari/Chrome)가 전달하는
 *      IME 조합 상태 코드인 `e.keyCode === 229`를 모두 검사하여 불필요한 조기 전송을 차단합니다.
 * 2. XSS (Cross-Site Scripting) 원천 차단:
 *    - 사용자의 질문과 AI의 답변을 DOM에 주입할 때 `innerHTML`을 일체 사용하지 않고,
 *      오직 `textContent` 프로퍼티만을 사용하여 악의적인 `<script>`, `onerror` 태그가 실행되지 않도록 합니다.
 * 3. 장애 복구 및 원클릭 재시도 (Fault Tolerance):
 *    - AI 서비스 일시 지연(504 Gateway Timeout) 또는 게이트웨이 오류(502 Bad Gateway) 발생 시,
 *      실패한 마지막 질문을 `lastFailedQuestion`에 캐싱하고 에러 배너와 함께 [재시도] 버튼을 노출합니다.
 *    - 사용자가 [재시도]를 클릭하면 실패했던 질문이 자동으로 입력창에 복원되고 즉시 재전송됩니다.
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chatForm");
    if (!form) return;

    // DOM 엘리먼트 참조
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSendBtn");
    const messagesContainer = document.getElementById("chatMessages");
    const charCounter = document.getElementById("charCounter");
    const errorBanner = document.getElementById("chatErrorBanner");
    const errorText = document.getElementById("chatErrorText");
    const retryBtn = document.getElementById("chatRetryBtn");
    const dismissErrorBtn = document.getElementById("chatDismissErrorBtn");

    // 상태 관리 변수
    let lastFailedQuestion = ""; // 재시도를 위해 보관하는 마지막 실패 질문 문자열
    let isSubmitting = false;     // API 요청 진행 중 여부 (중복 전송 플래그)
    let isComposing = false;      // 한글/CJK IME 문자 조합 중 여부

    /**
     * 대화 메시지 컨테이너의 스크롤을 항상 최하단으로 부드럽게 이동시킵니다.
     */
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    /**
     * 입력창 글자수 카운터를 갱신하고, 글자수 제한(1000자) 및 버튼 활성화 상태를 동기화합니다.
     * 또한 내용 길이에 따라 textarea의 높이를 최대 160px까지 자동 조절합니다.
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

    // 초기화 시 입력창 공백 정리 및 카운터 동기화
    if (chatInput) {
        if (chatInput.value) {
            chatInput.value = chatInput.value.trim();
        }
        updateCharCounter();
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
            e.preventDefault(); // 기본 줄바꿈 방지
            if (!sendBtn.disabled) {
                // 폼의 submit 이벤트를 트리거하여 질문 전송 실행
                form.dispatchEvent(new Event("submit", { cancelable: true }));
            }
        }
    });

    // 추천 질문(Quick Chip) 클릭 시 입력창 자동 완성 및 포커스
    document.querySelectorAll(".quick-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const question = chip.getAttribute("data-question");
            if (!question) return;
            chatInput.value = question;
            updateCharCounter();
            chatInput.focus();
        });
    });

    // 에러 배너 닫기 버튼 이벤트
    if (dismissErrorBtn) {
        dismissErrorBtn.addEventListener("click", () => {
            errorBanner.style.display = "none";
        });
    }

    // 통신 실패 후 [재시도] 버튼 클릭 시 마지막 질문 자동 복원 및 재전송
    if (retryBtn) {
        retryBtn.addEventListener("click", () => {
            if (lastFailedQuestion) {
                chatInput.value = lastFailedQuestion;
                updateCharCounter();
                errorBanner.style.display = "none";
                form.dispatchEvent(new Event("submit", { cancelable: true }));
            }
        });
    }

    /**
     * 대화 영역에 새로운 메시지 말풍선 DOM을 생성하여 추가합니다.
     *
     * [보안 설명]
     * - XSS 공격을 완전히 방지하기 위해 사용자 질문과 AI 답변 텍스트 모두
     *   `textContent`를 통해 안전하게 삽입합니다.
     *
     * @param {"user" | "ai"} role - 발화자 역할 ("user" 또는 "ai")
     * @param {string} text - 출력할 대화 본문 내용
     * @returns {HTMLElement} 생성된 말풍선 엘리먼트
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
        content.textContent = text; // textContent로 안전하게 삽입하여 악성 스크립트 실행 방지

        body.appendChild(author);
        body.appendChild(content);
        bubble.appendChild(avatar);
        bubble.appendChild(body);

        messagesContainer.appendChild(bubble);
        scrollToBottom();
        return bubble;
    }

    /**
     * AI 답변 생성 대기 중임을 나타내는 로딩 말풍선(애니메이션 도트 포함)을 생성합니다.
     */
    function showLoadingBubble() {
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble ai-bubble loading-bubble";
        bubble.id = "chatLoadingBubble";

        const avatar = document.createElement("div");
        avatar.className = "bubble-avatar";
        avatar.textContent = "🤖";

        const body = document.createElement("div");
        body.className = "bubble-body";

        const content = document.createElement("div");
        content.className = "bubble-content";

        // 타이핑 애니메이션 도트 엘리먼트 (순수 UI 효과)
        const typing = document.createElement("div");
        typing.className = "typing-dots";
        typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';

        content.appendChild(typing);
        body.appendChild(content);
        bubble.appendChild(avatar);
        bubble.appendChild(body);

        messagesContainer.appendChild(bubble);
        scrollToBottom();
    }

    /**
     * AI 응답 수신 완료 또는 에러 발생 시 로딩 말풍선을 DOM에서 제거합니다.
     */
    function hideLoadingBubble() {
        const loading = document.getElementById("chatLoadingBubble");
        if (loading) loading.remove();
    }

    /**
     * 질문 전송 폼 제출 이벤트 핸들러.
     * 질문 검증, 사용자 말풍선 추가, 백엔드 비동기 통신(`/api/chat`),
     * AI 답변 말풍선 추가 및 에러/재시도 상태를 통합 제어합니다.
     */
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const rawQuestion = chatInput.value;
        const question = rawQuestion.trim();

        // 공백 질문, 1000자 초과, 또는 이미 전송 중인 경우 무시
        if (!question || question.length > 1000 || isSubmitting) return;

        // 1. UI 상태 잠금 (중복 전송 방지)
        isSubmitting = true;
        sendBtn.disabled = true;
        chatInput.disabled = true;
        errorBanner.style.display = "none";

        // 2. 사용자 질문 말풍선 즉시 렌더링
        appendMessage("user", question);

        // 3. 입력창 초기화 및 높이 리셋
        chatInput.value = "";
        updateCharCounter();

        // 4. AI 답변 대기 로딩 표시기 출력
        showLoadingBubble();

        // 5. 백엔드 AI 채팅 API 호출
        const res = await apiRequest("/api/chat", {
            method: "POST",
            body: { question },
        });

        // 로딩 표시기 제거
        hideLoadingBubble();

        // 6. 응답 결과 처리
        if (res.ok && res.data && res.data.answer) {
            // 성공: AI 답변 말풍선 추가 및 실패 캐시 초기화
            appendMessage("ai", res.data.answer);
            lastFailedQuestion = "";
        } else {
            // 실패: docs/FRONTEND.md 규격에 따라 에러 메시지 구성 및 재시도 버튼 제어
            lastFailedQuestion = question;
            let msg = getErrorMessage(res.data, "오류가 발생했습니다.");

            if (res.status === 504) {
                // 시간 초과 (Gateway Timeout)
                msg = "AI 응답이 지연되어 답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요.";
                retryBtn.style.display = "inline-flex";
            } else if (res.status === 502) {
                // 서비스 연결 실패 (Bad Gateway)
                msg = "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.";
                retryBtn.style.display = "inline-flex";
            } else if (res.status === 401) {
                // 세션 만료 시 로그인 페이지로 이동
                window.location.assign("/login");
                return;
            } else {
                // 기타 클라이언트 오류 등은 재시도 버튼 숨김
                retryBtn.style.display = "none";
            }

            errorText.textContent = msg;
            errorBanner.style.display = "flex";
        }

        // 7. UI 잠금 해제 및 입력창으로 포커스 복귀
        isSubmitting = false;
        chatInput.disabled = false;
        updateCharCounter();
        chatInput.focus();
    });
});
