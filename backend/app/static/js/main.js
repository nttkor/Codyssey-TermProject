/**
 * AskMate 메인 클라이언트 스크립트 및 API 연동 참조 구현 (main.js)
 *
 * [파일 개요]
 * 본 파일은 프론트엔드 환경에서 AskMate 백엔드 REST API(/api/signup 등)와 통신하는
 * 표준적인 비동기(fetch) 호출 패턴과 에러 처리 방식을 보여주는 참조 예제 모듈입니다.
 *
 * [주요 기술적 설명]
 * 1. CSRF 방어 헤더 명시:
 *    - POST 요청 시 'X-Requested-With: XMLHttpRequest' 헤더를 필수 전송하여
 *      서버 측의 CSRF 가드(require_csrf_header)를 통과합니다.
 * 2. 복합 에러 응답 파싱:
 *    - 백엔드의 422 Unprocessable Entity(Pydantic 검증 오류)는 배열(Array) 형태의 상세 에러를 반환하고,
 *      409 Conflict(아이디 중복) 등 일반 예외는 단일 문자열(String) 형태의 detail을 반환합니다.
 *    - 응답 데이터 형식에 따라 유연하게 에러 메시지를 조합하여 화면에 표시할 수 있도록 구현되어 있습니다.
 * 3. 보안 모범 사례:
 *    - 비밀번호는 브라우저 단에서 임의로 trim()하지 않고 사용자가 입력한 그대로 전송합니다.
 *    - 가입 성공 후 자동 세션을 발급하지 않으므로 명시적인 로그인 절차가 필요합니다.
 */

/**
 * 회원가입 API(/api/signup)를 비동기 호출하여 신규 계정을 생성합니다.
 *
 * @param {string} username - 사용자 계정 아이디 (영문, 숫자, 밑줄 허용)
 * @param {string} password - 사용자 평문 비밀번호 (최소 8자 이상)
 * @returns {Promise<Object>} 성공 시 서버가 반환한 사용자 정보 객체 { id: number, username: string }
 * @throws {Error} 유효성 검증 실패(422), 중복 가입(409), 서버 장애(500) 시 에러 메시지 throw
 */
async function signupUser(username, password) {
    // 백엔드 엔드포인트로 JSON POST 요청 전송
    const response = await fetch("/api/signup", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest", // CSRF 방어용 필수 헤더
        },
        body: JSON.stringify({ username, password }),
    });

    // 서버 JSON 응답 파싱
    const data = await response.json();

    if (!response.ok) {
        // 응답 상태가 2xx가 아닌 경우 에러 메시지 추출
        // 입력 검증(422)은 배열({loc, msg, type} 객체 목록), 중복 가입(409) 등은 단일 문자열입니다.
        const message = Array.isArray(data.detail)
            ? data.detail.map((error) => error.msg).join("\n")
            : data.detail;
        throw new Error(message || "회원가입 요청 처리에 실패했습니다.");
    }

    return data; // { id, username }. 회원가입 시 자동 로그인 세션은 발급되지 않습니다.
}

/* [사용 예시] 회원가입 폼의 비동기 submit 이벤트 리스너에서의 활용:
event.preventDefault();
try {
    const user = await signupUser(username, password);
    // 가입 완료 안내 메시지를 표시하거나 로그인 페이지(/login)로 이동합니다.
} catch (error) {
    // XSS 방지를 위해 innerHTML 대신 textContent를 사용하여 에러 메시지를 화면에 안전하게 렌더링합니다.
    errorElement.textContent = error.message;
}
*/
