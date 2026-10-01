/**
 * AskMate 회원가입 화면 전용 클라이언트 스크립트 (signup.js)
 *
 * [파일 개요]
 * 본 모듈은 회원가입 화면(`/signup`)의 사용자 입력 유효성 검사, 비밀번호 실시간 일치 여부 피드백,
 * 비동기 회원가입 API(`/api/signup`) 호출 및 가입 성공/실패 시의 UI 전환을 처리합니다.
 *
 * [주요 기술적 설명]
 * 1. 실시간 입력 피드백 (`checkPasswordMatch`):
 *    - 사용자가 비밀번호와 비밀번호 확인 필드를 입력할 때마다 `input` 이벤트를 감지하여
 *      일치 여부를 텍스트 및 클래스(`hint-success`, `hint-error`)로 즉시 안내합니다.
 * 2. 프론트엔드 선행 유효성 검사 (Client-side Validation):
 *    - 아이디 규칙: 3~30자의 영문 대소문자, 숫자, 밑줄(_) 정규식 검증 및 소문자 정규화.
 *    - 비밀번호 규칙: 최소 8자 이상 128자 이하 길이 검증. (비밀번호 원본 공백 유지를 위해 trim 금지)
 *    - 비밀번호 일치 검사: 확인 필드와의 정확한 일치 검증.
 * 3. 폼 제출 상태 관리 및 UX 최적화:
 *    - 전송 중 버튼 비활성화(`disabled`) 및 로딩 스피너 활성화로 중복 제출 방지.
 *    - 가입 성공 시(HTTP 201) 성공 메시지를 표시하고, `?registered=1` 파라미터와 함께
 *      로그인 페이지(`/login`)로 부드럽게 이동하여 사용자가 바로 로그인할 수 있도록 지원합니다.
 *    - 409 Conflict 발생 시 명확하게 "이미 사용 중인 사용자명입니다."를 경고창에 표시합니다.
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("signupForm");
    if (!form) return;

    // DOM 엘리먼트 참조
    const usernameInput = document.getElementById("signupUsername");
    const passwordInput = document.getElementById("signupPassword");
    const passwordConfirmInput = document.getElementById("signupPasswordConfirm");
    const passwordMatchHint = document.getElementById("passwordMatchHint");
    const submitBtn = document.getElementById("signupSubmitBtn");
    const alertBox = document.getElementById("signupAlert");

    /**
     * 비밀번호와 비밀번호 확인 입력값의 일치 여부를 실시간으로 판별하여 힌트 문구를 갱신합니다.
     */
    function checkPasswordMatch() {
        const pw = passwordInput.value;
        const confirm = passwordConfirmInput.value;

        // 비밀번호 확인 칸이 아직 비어있으면 힌트를 비웁니다.
        if (!confirm) {
            passwordMatchHint.textContent = "";
            passwordMatchHint.className = "form-hint";
            return;
        }

        // 비밀번호 일치 여부에 따른 안내 문구 및 스타일 적용
        if (pw === confirm) {
            passwordMatchHint.textContent = "✓ 비밀번호가 일치합니다.";
            passwordMatchHint.className = "form-hint hint-success";
        } else {
            passwordMatchHint.textContent = "✗ 비밀번호가 일치하지 않습니다.";
            passwordMatchHint.className = "form-hint hint-error";
        }
    }

    // 비밀번호 입력 이벤트 리스너 등록
    passwordInput.addEventListener("input", checkPasswordMatch);
    passwordConfirmInput.addEventListener("input", checkPasswordMatch);

    /**
     * 회원가입 폼 제출 이벤트 핸들러.
     * 클라이언트 유효성 검사 통과 시 백엔드 `/api/signup`으로 POST 요청을 전송합니다.
     */
    form.addEventListener("submit", async (e) => {
        e.preventDefault(); // 기본 폼 제출 동작(페이지 새로고침) 방지

        // 사용자 입력값 정제
        const rawUsername = usernameInput.value.trim();
        const username = rawUsername.toLowerCase(); // 대소문자 혼동 방지를 위해 소문자로 통일
        const password = passwordInput.value;        // 비밀번호는 의도적 공백 유지를 위해 trim() 금지
        const passwordConfirm = passwordConfirmInput.value;

        // 1. 아이디 형식 유효성 검사 (3~30자의 영문, 숫자, 밑줄)
        const usernamePattern = /^[a-zA-Z0-9_]{3,30}$/;
        if (!usernamePattern.test(username)) {
            alertBox.className = "alert alert-danger";
            alertBox.textContent = "아이디는 3~30자의 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.";
            alertBox.style.display = "flex";
            usernameInput.focus();
            return;
        }

        // 2. 비밀번호 길이 정책 검사 (8자 이상 128자 이하)
        if (password.length < 8 || password.length > 128) {
            alertBox.className = "alert alert-danger";
            alertBox.textContent = "비밀번호는 8자 이상 128자 이하로 입력해 주세요.";
            alertBox.style.display = "flex";
            passwordInput.focus();
            return;
        }

        // 3. 비밀번호 재확인 일치 검사
        if (password !== passwordConfirm) {
            alertBox.className = "alert alert-danger";
            alertBox.textContent = "비밀번호와 비밀번호 확인 입력값이 일치하지 않습니다.";
            alertBox.style.display = "flex";
            passwordConfirmInput.focus();
            return;
        }

        // 4. 전송 진행 상태 UI 잠금 (버튼 비활성화 및 스피너 표시)
        submitBtn.disabled = true;
        const btnText = submitBtn.querySelector(".btn-text");
        const btnSpinner = submitBtn.querySelector(".btn-spinner");
        if (btnText) btnText.style.display = "none";
        if (btnSpinner) btnSpinner.style.display = "inline";
        alertBox.style.display = "none";

        // 5. 백엔드 회원가입 API 비동기 호출
        // 클라이언트 전송 페이로드에는 username과 password만 포함합니다.
        const res = await apiRequest("/api/signup", {
            method: "POST",
            body: { username, password },
        });

        // 6. 응답 결과 처리
        if (res.status === 201) {
            // 회원가입 성공: 안내 메시지 출력 후 로그인 화면으로 이동
            alertBox.className = "alert alert-success";
            alertBox.textContent = "회원가입이 완료되었습니다! 로그인 페이지로 이동합니다...";
            alertBox.style.display = "flex";
            setTimeout(() => {
                window.location.assign("/login?registered=1");
            }, 600);
        } else {
            // 회원가입 실패: 오류 메시지 표시 및 버튼 복원
            alertBox.className = "alert alert-danger";
            if (res.status === 409) {
                alertBox.textContent = "이미 사용 중인 사용자명입니다.";
            } else {
                alertBox.textContent = getErrorMessage(res.data, "회원가입에 실패했습니다.");
            }
            alertBox.style.display = "flex";

            // 버튼 UI 상태 원복
            submitBtn.disabled = false;
            if (btnText) btnText.style.display = "inline";
            if (btnSpinner) btnSpinner.style.display = "none";
        }
    });
});
