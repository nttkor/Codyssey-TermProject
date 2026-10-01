/**
 * AskMate 대화 기록 화면 전용 클라이언트 스크립트 (history.js)
 *
 * [파일 개요]
 * 본 모듈은 대화 기록 화면(`/history`)에서 사용자의 과거 질문과 AI 답변 전체 목록을
 * 백엔드 API(`/api/me/chats`)로부터 비동기 조회하여 최신순으로 화면에 렌더링합니다.
 * 로딩 상태, 빈 상태(Empty State), 에러 상태를 각각 분기 처리하며,
 * 시간 정보의 현지화 포맷팅 및 XSS 공격 방어 로직을 포함합니다.
 *
 * [핵심 기술적 설명]
 * 1. 상태 기반 뷰 제어 (State-driven UI Transition):
 *    - 데이터 조회 전: `historyLoading` 표시, 목록/빈 상태/에러 상태 숨김.
 *    - 데이터가 비어 있는 경우: `historyEmpty` 표시로 신규 사용자에게 대화 시작 유도.
 *    - 데이터가 존재하는 경우: 총 대화 건수(`historyCountText`) 갱신 및 카드 목록 표시.
 *    - 조회 실패 시: 에러 메시지와 함께 [다시 시도] 버튼 제공.
 * 2. 한국어 로케일 시각 변환 (`toLocaleString('ko-KR')`):
 *    - 백엔드가 반환한 ISO 8601 UTC 시각 문자열을 브라우저의 `Date` 객체로 파싱하여
 *      사용자의 현지 시간대(KST 등)에 맞는 친숙한 한국어 포맷(예: "2026년 9월 20일 오전 03:00")으로 변환합니다.
 * 3. XSS 방어:
 *    - 대화 기록 카드 내 질문 및 답변 텍스트를 DOM에 추가할 때 `textContent`만을 사용하여
 *      임의의 스크립트 인젝션을 원천 차단합니다.
 */

document.addEventListener("DOMContentLoaded", () => {
    const listContainer = document.getElementById("historyListContainer");
    if (!listContainer) return;

    // DOM 엘리먼트 참조
    const loadingState = document.getElementById("historyLoading");
    const emptyState = document.getElementById("historyEmpty");
    const errorAlert = document.getElementById("historyError");
    const errorMessage = document.getElementById("historyErrorMessage");
    const retryBtn = document.getElementById("historyRetryBtn");
    const refreshBtn = document.getElementById("historyRefreshBtn");
    const itemsContainer = document.getElementById("historyItems");
    const countText = document.getElementById("historyCountText");

    /**
     * 백엔드 대화 기록 API(`/api/me/chats`)를 호출하고 화면에 카드 리스트를 렌더링합니다.
     */
    async function fetchHistory() {
        // UI 상태 초기화: 로딩 인디케이터 표시
        loadingState.style.display = "flex";
        emptyState.style.display = "none";
        listContainer.style.display = "none";
        errorAlert.style.display = "none";

        // GET /api/me/chats 호출 (세션 쿠키 기반 조회)
        const res = await apiRequest("/api/me/chats", { method: "GET" });

        // 로딩 완료 후 스피너 숨김
        loadingState.style.display = "none";

        // 401 세션 만료 시 로그인 페이지로 이동
        if (res.status === 401) {
            window.location.assign("/login");
            return;
        }

        // 서버 오류 등 비정상 응답 처리
        if (!res.ok) {
            errorMessage.textContent = getErrorMessage(res.data, "대화 기록을 불러오지 못했습니다.");
            errorAlert.style.display = "flex";
            return;
        }

        const chats = res.data;

        // 대화 기록이 없는 경우: 빈 상태 뷰(Empty State) 표시
        if (!Array.isArray(chats) || chats.length === 0) {
            emptyState.style.display = "flex";
            return;
        }

        // 대화 기록이 있는 경우: 카드 목록 동적 렌더링
        countText.textContent = `총 ${chats.length}건의 대화`;
        itemsContainer.innerHTML = ""; // 기존 목록 초기화

        chats.forEach((item, index) => {
            // 대화 카드 래퍼 생성
            const card = document.createElement("div");
            card.className = "history-card";

            // 카드 헤더 (생성 시각 및 대화 번호 표시)
            const header = document.createElement("div");
            header.className = "history-card-header";

            // 시각 포맷팅 (UTC -> 사용자 현지 시각)
            const timeSpan = document.createElement("span");
            try {
                timeSpan.textContent = new Date(item.created_at).toLocaleString("ko-KR", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                });
            } catch (e) {
                // 파싱 오류 발생 시 원본 문자열 fallback
                timeSpan.textContent = item.created_at;
            }

            // 역순 번호 표기 (#총개수, #총개수-1, ...)
            const idSpan = document.createElement("span");
            idSpan.textContent = `#${chats.length - index}`;

            header.appendChild(timeSpan);
            header.appendChild(idSpan);

            // 질문 블록 (XSS 방지를 위해 textContent 사용)
            const qBlock = document.createElement("div");
            qBlock.className = "history-block";

            const qLabel = document.createElement("div");
            qLabel.className = "history-label label-question";
            qLabel.textContent = "👤 질문";

            const qText = document.createElement("div");
            qText.className = "history-text question-text";
            qText.textContent = item.question; // 안전한 텍스트 바인딩

            qBlock.appendChild(qLabel);
            qBlock.appendChild(qText);

            // 답변 블록 (XSS 방지를 위해 textContent 사용)
            const aBlock = document.createElement("div");
            aBlock.className = "history-block";

            const aLabel = document.createElement("div");
            aLabel.className = "history-label label-answer";
            aLabel.textContent = "🤖 AI 답변";

            const aText = document.createElement("div");
            aText.className = "history-text answer-text";
            aText.textContent = item.answer; // 안전한 텍스트 바인딩

            aBlock.appendChild(aLabel);
            aBlock.appendChild(aText);

            // 요소 결합 후 컨테이너에 추가
            card.appendChild(header);
            card.appendChild(qBlock);
            card.appendChild(aBlock);

            itemsContainer.appendChild(card);
        });

        // 렌더링 완료된 목록 컨테이너 표시
        listContainer.style.display = "flex";
    }

    // 새로고침 및 재시도 버튼 이벤트 바인딩
    if (refreshBtn) refreshBtn.addEventListener("click", fetchHistory);
    if (retryBtn) retryBtn.addEventListener("click", fetchHistory);

    // 페이지 진입 시 최초 1회 대화 내역 로드
    fetchHistory();
});
