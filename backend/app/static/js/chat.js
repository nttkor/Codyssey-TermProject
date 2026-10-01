/**
 * AskMate 채팅 화면 전용 스크립트 (chat.js)
 * POST /api/chat 호출, 1000자 제한, 로딩 인디케이터, 502/504 재시도, XSS 방지
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chatForm");
    if (!form) return;

    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSendBtn");
    const messagesContainer = document.getElementById("chatMessages");
    const charCounter = document.getElementById("charCounter");
    const errorBanner = document.getElementById("chatErrorBanner");
    const errorText = document.getElementById("chatErrorText");
    const retryBtn = document.getElementById("chatRetryBtn");
    const dismissErrorBtn = document.getElementById("chatDismissErrorBtn");

    let lastFailedQuestion = "";
    let isSubmitting = false;
    let isComposing = false;

    // 스크롤 맨 아래로 이동
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // 글자수 카운터 및 버튼 활성화 제어
    function updateCharCounter() {
        const length = chatInput.value.length;
        const trimmed = chatInput.value.trim();
        charCounter.textContent = `${length} / 1000자`;

        if (length > 1000) {
            charCounter.classList.add("limit-exceeded");
            sendBtn.disabled = true;
        } else {
            charCounter.classList.remove("limit-exceeded");
            sendBtn.disabled = isSubmitting || trimmed.length === 0;
        }

        // 높이 자동 조절
        chatInput.style.height = "auto";
        chatInput.style.height = `${Math.min(chatInput.scrollHeight, 160)}px`;
    }

    // [추가] 초기화 시 입력창 공백 제거 및 상태 업데이트
    if (chatInput) {
        if (chatInput.value) {
            chatInput.value = chatInput.value.trim();
        }
        updateCharCounter();
    }

    chatInput.addEventListener("input", updateCharCounter);
    chatInput.addEventListener("compositionstart", () => { isComposing = true; });
    chatInput.addEventListener("compositionend", () => { isComposing = false; });

    // Enter 키로 전송 (Shift+Enter는 줄바꿈)
    chatInput.addEventListener("keydown", (e) => {
        // IME 조합 확정 Enter는 전송이 아니다. 일부 브라우저는 keyCode 229만 전달한다.
        if (isComposing || e.isComposing || e.keyCode === 229) return;
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                form.dispatchEvent(new Event("submit", { cancelable: true }));
            }
        }
    });

    // 추천 질문 칩 클릭
    document.querySelectorAll(".quick-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            const question = chip.getAttribute("data-question");
            if (!question) return;
            chatInput.value = question;
            updateCharCounter();
            chatInput.focus();
        });
    });

    // 에러 배너 닫기
    if (dismissErrorBtn) {
        dismissErrorBtn.addEventListener("click", () => {
            errorBanner.style.display = "none";
        });
    }

    // 재시도 버튼 클릭
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

    // 말풍선 DOM 추가 (XSS 방지: 질문/답변 모두 textContent 사용)
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
        content.textContent = text; // textContent로 안전하게 삽입

        body.appendChild(author);
        body.appendChild(content);
        bubble.appendChild(avatar);
        bubble.appendChild(body);

        messagesContainer.appendChild(bubble);
        scrollToBottom();
        return bubble;
    }

    // AI 로딩 인디케이터 말풍선 생성
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

    function hideLoadingBubble() {
        const loading = document.getElementById("chatLoadingBubble");
        if (loading) loading.remove();
    }

    // 질문 제출 핸들러
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const rawQuestion = chatInput.value;
        const question = rawQuestion.trim();

        if (!question || question.length > 1000 || isSubmitting) return;

        // UI 상태 잠금
        isSubmitting = true;
        sendBtn.disabled = true;
        chatInput.disabled = true;
        errorBanner.style.display = "none";

        // 사용자 메시지 추가
        appendMessage("user", question);

        // 입력창 비우기
        chatInput.value = "";
        updateCharCounter();

        // AI 로딩 표시
        showLoadingBubble();

        const res = await apiRequest("/api/chat", {
            method: "POST",
            body: { question },
        });

        hideLoadingBubble();

        if (res.ok && res.data && res.data.answer) {
            // 성공: AI 답변 표시
            appendMessage("ai", res.data.answer);
            lastFailedQuestion = "";
        } else {
            // 실패: docs/FRONTEND.md 규격에 따라 처리
            lastFailedQuestion = question;
            let msg = getErrorMessage(res.data, "오류가 발생했습니다.");

            if (res.status === 504) {
                msg = "AI 응답이 지연되어 답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요.";
                retryBtn.style.display = "inline-flex";
            } else if (res.status === 502) {
                msg = "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.";
                retryBtn.style.display = "inline-flex";
            } else if (res.status === 401) {
                window.location.assign("/login");
                return;
            } else {
                retryBtn.style.display = "none";
            }

            errorText.textContent = msg;
            errorBanner.style.display = "flex";
        }

        // UI 잠금 해제
        isSubmitting = false;
        chatInput.disabled = false;
        updateCharCounter();
        chatInput.focus();
    });
});
