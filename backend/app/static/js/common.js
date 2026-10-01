/**
 * AskMate 공통 클라이언트 라이브러리 (common.js)
 *
 * [파일 개요]
 * 본 모듈은 AskMate 웹 애플리케이션의 모든 페이지에서 공통으로 로드되는 기반 스크립트입니다.
 * 백엔드 REST API와의 안전한 비동기 통신을 담당하는 `apiRequest` 래퍼 함수를 비롯하여,
 * CSRF 방어 헤더 자동 주입, 세션 만료(401) 감지 시 자동 리다이렉트, 오류 메시지 정규화,
 * 비밀번호 가시성 토글, 네비게이션 바 로그아웃 이벤트 처리 기능을 통합 제공합니다.
 *
 * [주요 기술적 설명]
 * 1. 안전한 통신 래퍼 (`apiRequest`):
 *    - POST, PUT, DELETE 등 상태 변경 HTTP 메서드 감지 시 `X-Requested-With: XMLHttpRequest` 헤더 자동 첨부.
 *    - 객체 형태의 body 데이터를 자동으로 JSON 직렬화(`JSON.stringify`).
 *    - 204 No Content 응답 처리: 본문이 없는 응답에 대해 `response.json()` 호출을 생략하여 파싱 에러 방지.
 *    - 401 Unauthorized 감지: 세션 만료 시 로그인 화면으로 즉각 리다이렉션(`window.location.assign`).
 *      (단, 로그인 시도 자체에서 발생한 401은 화면 에러 출력을 위해 `skipAuthRedirect` 옵션으로 우회)
 * 2. XSS 및 렌더링 보안:
 *    - 서버에서 전달받은 에러 메시지를 파싱할 때 HTML 마크업이 포함되어도 안전하도록
 *      `textContent`로 화면에 바인딩할 수 있는 문자열 형태로 가공(`getErrorMessage`).
 * 3. 중복 요청 방지 (Double-submit Prevention):
 *    - 로그아웃 등 네트워크 통신 진행 중 버튼을 비활성화(`disabled = true`)하여 연타로 인한 중복 호출 방지.
 */

/**
 * 백엔드 API 엔드포인트와 통신하는 공통 HTTP 클라이언트 함수.
 *
 * [기술 설명]
 * - 기본 헤더로 `Content-Type: application/json`을 설정합니다.
 * - HTTP 사양상 안전하지 않은 메서드(GET, HEAD 제외)인 경우 `X-Requested-With: XMLHttpRequest` 헤더를 자동 주입합니다.
 * - 401 상태 코드 수신 시, 사용자가 로그인 페이지가 아닌 곳에 머물러 있다면 자동으로 `/login`으로 이동시킵니다.
 *
 * @param {string} url - 요청 대상 API 엔드포인트 URL (예: "/api/chat", "/api/logout")
 * @param {Object} [options={}] - fetch 옵션 객체 (method, headers, body, skipAuthRedirect 등)
 * @param {boolean} [options.skipAuthRedirect=false] - 401 수신 시 로그인 화면으로 자동 이동하지 않고 호출자에게 결과를 그대로 반환할지 여부
 * @returns {Promise<{ok: boolean, status: number, data: any}>} 응답 결과 래퍼 객체
 */
async function apiRequest(url, options = {}) {
    const defaultHeaders = {
        "Content-Type": "application/json",
    };

    // POST, PUT, DELETE 요청에 X-Requested-With: XMLHttpRequest 헤더 필수 주입 (docs/FRONTEND.md)
    const method = (options.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
        defaultHeaders["X-Requested-With"] = "XMLHttpRequest";
    }

    options.headers = {
        ...defaultHeaders,
        ...(options.headers || {}),
    };

    // body가 순수 객체(Plain Object)인 경우 JSON 문자열로 자동 변환
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    }

    try {
        const response = await fetch(url, options);

        // 401: 비로그인 또는 세션 만료 (로그인 요청 등은 skipAuthRedirect로 실제 응답을 그대로 사용)
        if (response.status === 401 && !options.skipAuthRedirect) {
            if (window.location.pathname !== "/login") {
                window.location.assign("/login");
            }
            return { ok: false, status: 401, data: { detail: "로그인이 필요합니다." } };
        }

        // 204: 내용 없음 (로그아웃 등). JSON 파싱 시 SyntaxError가 발생하므로 건너뜁니다.
        if (response.status === 204) {
            return { ok: true, status: 204, data: null };
        }

        // Content-Type에 JSON이 명시된 경우에만 본문 파싱 수행
        let data = null;
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
            data = await response.json();
        }

        return {
            ok: response.ok,
            status: response.status,
            data: data,
        };
    } catch (error) {
        // 네트워크 연결 두절(오프라인), DNS 오류 등 fetch 자체 실패 시 status 0 반환
        return {
            ok: false,
            status: 0,
            data: { detail: error.message || "네트워크 연결에 실패했습니다." },
        };
    }
}

/**
 * 서버가 반환한 에러 응답 객체로부터 사람이 읽을 수 있는 단일 에러 문자열을 추출합니다.
 *
 * [기술 설명]
 * - Pydantic 유효성 검사 에러 배열인 경우 각 항목의 `msg`를 개행 문자(`\n`)로 결합합니다.
 * - 단일 문자열 detail인 경우 그대로 반환하며, 데이터가 없거나 형식이 다르면 fallback 기본 문구를 반환합니다.
 *
 * @param {Object} data - 서버가 반환한 JSON 파싱 데이터 객체
 * @param {string} [fallback="오류가 발생했습니다. 잠시 후 다시 시도해 주세요."] - 메시지 추출 실패 시 기본 문구
 * @returns {string} 화면에 출력 가능한 정제된 에러 메시지
 */
function getErrorMessage(data, fallback = "오류가 발생했습니다. 잠시 후 다시 시도해 주세요.") {
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
        return data.detail.map((err) => err.msg || JSON.stringify(err)).join("\n");
    }
    return fallback;
}

/**
 * 비밀번호 입력 필드의 표시/숨김(type="password" <-> type="text") 토글 버튼 이벤트를 초기화합니다.
 *
 * [기술 설명]
 * - `.toggle-password` 클래스를 가진 모든 버튼을 탐색하여 클릭 리스너를 바인딩합니다.
 * - 버튼의 `data-target` 속성에 지정된 input id를 찾아 input type을 변경하고 아이콘을 전환합니다.
 */
function initPasswordToggles() {
    document.querySelectorAll(".toggle-password").forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (!input) return;

            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            btn.textContent = isPassword ? "🔒" : "👁️";
        });
    });
}

/**
 * 상단 네비게이션 바의 로그아웃 버튼 이벤트 및 에러 메시지 표시를 초기화합니다.
 *
 * [기술 설명]
 * 1. 로그아웃 버튼 클릭 시 즉시 버튼을 비활성화(`disabled = true`)하여 중복 클릭을 차단합니다.
 * 2. `/api/logout`에 POST 요청을 전송하고, 204 No Content를 받으면 로그인 화면(`/login`)으로 이동합니다.
 * 3. 요청 실패 시 `logoutError` 영역에 텍스트 형태로 안전하게 안내 문구를 표시합니다.
 * 4. 작업 완료 후 `finally` 블록에서 버튼을 다시 활성화합니다.
 */
function initNavbar() {
    const logoutBtn = document.getElementById("navLogoutBtn");
    const logoutError = document.getElementById("logoutError");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            if (logoutBtn.disabled) return;
            logoutBtn.disabled = true; // 중복 전송 방지 잠금
            if (logoutError) logoutError.style.display = "none";
            try {
                const res = await apiRequest("/api/logout", {
                    method: "POST",
                    skipAuthRedirect: true, // 401이라도 수동 제어
                });
                if (res.ok && res.status === 204) {
                    window.location.assign("/login");
                    return;
                }
                if (logoutError) {
                    logoutError.textContent = "로그아웃에 실패했습니다. 연결 상태를 확인하고 다시 시도해 주세요.";
                    logoutError.style.display = "flex";
                }
            } finally {
                logoutBtn.disabled = false; // 버튼 상태 복원
            }
        });
    }
}

// DOM 문서 로드 완료 시 공통 UI 컴포넌트 자동 초기화
document.addEventListener("DOMContentLoaded", () => {
    initPasswordToggles();
    initNavbar();
});
