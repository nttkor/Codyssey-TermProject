/**
 * AskMate 로그인 화면 전용 클라이언트 스크립트 (login.js)
 *
 * [파일 개요]
 * 본 모듈은 로그인 화면(`/login`)의 사용자 인증 입력 폼 제어, 회원가입 완료 파라미터(`?registered=1`) 처리,
 * 비동기 로그인 API(`/api/login`) 호출 및 로그인 성공/실패 시의 UI 전환을 담당합니다.
 *
 * [주요 기술적 설명]
 * 1. 가입 완료 쿼리 파라미터 감지:
 *    - `URLSearchParams`를 통해 URL의 `registered=1` 쿼리를 확인하여,
 *      회원가입 직후 넘어온 신규 회원에게 성공 알림 배너를 즉시 노출합니다.
 * 2. 비밀번호 무수정 전송:
 *    - 아이디는 `trim()`으로 정리하지만, 비밀번호는 사용자가 지정한 특수 공백이 유실되지 않도록
 *      원본 그대로 전송하여 인증 실패를 방지합니다.
 * 3. `skipAuthRedirect: true` 옵션 적용:
 *    - 로그인 시도 시 401 Unauthorized가 반환되는 것은 비정상 세션 만료가 아니라
 *      자격 증명 불일치(비밀번호 오류 등)이므로, 자동 리다이렉트를 막고 화면에 에러를 표시합니다.
 * 4. 실패 시 보안 및 UX 조치:
 *    - 로그인 실패 시 입력된 비밀번호 필드를 비우고(`value = ""`) 즉시 포커스(`focus()`)를 주어
 *      사용자가 비밀번호를 재입력하기 편하도록 유도합니다.
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("loginForm");
    if (!form) return;

    // DOM 엘리먼트 참조
    const usernameInput = document.getElementById("loginUsername");
    const passwordInput = document.getElementById("loginPassword");
    const submitBtn = document.getElementById("loginSubmitBtn");
    const alertBox = document.getElementById("loginAlert");

    // 1. URL에 ?registered=1 파라미터가 존재하면 회원가입 완료 축하 안내 배너 표시
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("registered") === "1") {
        alertBox.className = "alert alert-success";
        alertBox.textContent = "회원가입이 완료되었습니다! 발급받은 아이디와 비밀번호로 로그인해 주세요.";
        alertBox.style.display = "flex";
    }

    /**
     * 로그인 폼 제출 이벤트 핸들러.
     * 입력값 검증 후 백엔드 `/api/login` 엔드포인트로 POST 요청을 수행합니다.
     */
    form.addEventListener("submit", async (e) => {
        e.preventDefault(); // 기본 폼 새로고침 동작 방지

        const username = usernameInput.value.trim();
        const password = passwordInput.value; // 비밀번호는 원본 그대로 전송 (docs/API.md)

        // 필수 필드 입력 여부 확인
        if (!username || !password) {
            alertBox.className = "alert alert-danger";
            alertBox.textContent = "아이디와 비밀번호를 모두 입력해 주세요.";
            alertBox.style.display = "flex";
            return;
        }

        // 2. 제출 중 UI 잠금 (버튼 비활성화 및 스피너 표시)
        submitBtn.disabled = true;
        const btnText = submitBtn.querySelector(".btn-text");
        const btnSpinner = submitBtn.querySelector(".btn-spinner");
        if (btnText) btnText.style.display = "none";
        if (btnSpinner) btnSpinner.style.display = "inline";
        alertBox.style.display = "none";

        // 3. 백엔드 로그인 API 호출
        // skipAuthRedirect: true를 지정하여 401 응답 시 공통 리다이렉트 동작을 방지하고 에러 문구를 표시합니다.
        const res = await apiRequest("/api/login", {
            method: "POST",
            body: { username, password },
            skipAuthRedirect: true,
        });

        // 4. 응답 결과 분기 처리
        if (res.ok) {
            // 로그인 성공: 메인 대화 화면(/chat)으로 이동
            window.location.assign("/chat");
        } else {
            // 로그인 실패: 오류 메시지 출력 및 비밀번호 입력칸 초기화
            alertBox.className = "alert alert-danger";
            alertBox.textContent = getErrorMessage(res.data, "사용자명 또는 비밀번호가 올바르지 않습니다.");
            alertBox.style.display = "flex";

            // 버튼 상태 원복 및 비밀번호 재입력 유도
            submitBtn.disabled = false;
            if (btnText) btnText.style.display = "inline";
            if (btnSpinner) btnSpinner.style.display = "none";
            passwordInput.value = "";
            passwordInput.focus();
        }
    });
});
