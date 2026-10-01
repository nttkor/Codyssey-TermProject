/**
 * AskMate 공통 스크립트 (common.js)
 * API 클라이언트, CSRF 방지 헤더, 세션 인증 및 로그아웃
 */

// 안전한 API 요청 래퍼 함수
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

        // 204: 내용 없음 (로그아웃 등). JSON 파싱 시도 금지
        if (response.status === 204) {
            return { ok: true, status: 204, data: null };
        }

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
        return {
            ok: false,
            status: 0,
            data: { detail: error.message || "네트워크 연결에 실패했습니다." },
        };
    }
}

// 서버 오류 메시지 추출 유틸
function getErrorMessage(data, fallback = "오류가 발생했습니다. 잠시 후 다시 시도해 주세요.") {
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
        return data.detail.map((err) => err.msg || JSON.stringify(err)).join("\n");
    }
    return fallback;
}

// 비밀번호 표시/숨김 토글
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

// 네비게이션 및 로그아웃 초기화
function initNavbar() {
    const logoutBtn = document.getElementById("navLogoutBtn");
    const logoutError = document.getElementById("logoutError");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            if (logoutBtn.disabled) return;
            logoutBtn.disabled = true;
            if (logoutError) logoutError.style.display = "none";
            try {
                const res = await apiRequest("/api/logout", {
                    method: "POST",
                    skipAuthRedirect: true,
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
                logoutBtn.disabled = false;
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initPasswordToggles();
    initNavbar();
});
