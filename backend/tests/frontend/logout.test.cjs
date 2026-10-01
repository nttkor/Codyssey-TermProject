/**
 * AskMate 프론트엔드 로그아웃 기능 단위 테스트 (logout.test.cjs)
 *
 * [파일 개요]
 * 본 모듈은 Node.js 내장 테스트 러너(`node:test`)와 가상 머신(`node:vm`) 모듈을 활용하여,
 * 브라우저나 무거운 DOM 라이브러리(jsdom 등) 설치 없이 가상의 DOM 및 fetch 환경을 모킹하고
 * `common.js`에 정의된 `initNavbar` 및 로그아웃 동작을 단위 검증합니다.
 *
 * [실행 방법]
 * node --test backend/tests/frontend/*.test.cjs
 *
 * [주요 검증 항목]
 * 1. 204 No Content 성공 시:
 *    - POST /api/logout 호출 및 `X-Requested-With: XMLHttpRequest` 헤더 전송 확인.
 *    - 로그인 페이지(`/login`)로 정상 리다이렉트(`window.location.assign`)되는지 확인.
 * 2. 실패 응답(200, 401, 403, 500) 시:
 *    - 페이지 이동 없이 에러 안내 메시지가 화면에 표시되는지 확인.
 *    - 에러 메시지에 HTML 태그가 삽입되어도 XSS 취약점이 발생하지 않는지 확인.
 *    - 실패 후 사용자가 다시 클릭할 수 있도록 버튼 활성화 상태(`disabled = false`) 복원 확인.
 * 3. 비동기 처리 중 중복 전송 방지 및 네트워크 복구:
 *    - 요청 진행 중 버튼이 비활성화(`disabled = true`)되어 연타를 방지하는지 확인.
 *    - 네트워크 오류 후 재시도 시 정상 완료되는지 확인.
 */

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');

/**
 * Node.js vm 환경에 가상 브라우저 객체(window, document, fetch)를 주입하고 common.js를 실행하는 헬퍼 함수.
 *
 * @param {Function} fetch - 모킹된 비동기 fetch 함수
 * @returns {{click: Function, button: Object, error: Object, redirects: Array<string>}}
 */
function setup(fetch) {
    let click;
    const button = { disabled: false, addEventListener: (_, handler) => { click = handler; } };
    const error = { style: { display: 'none' }, textContent: '' };
    const redirects = [];
    const context = vm.createContext({
        document: {
            addEventListener() {},
            getElementById: id => id === 'navLogoutBtn' ? button : error,
        },
        window: { location: { pathname: '/chat', assign: url => redirects.push(url) } },
        fetch,
        FormData: class {},
    });
    // common.js 코드를 가상 컨텍스트에서 실행
    vm.runInContext(readFileSync(resolve(__dirname, '../../app/static/js/common.js'), 'utf8'), context);
    vm.runInContext('initNavbar()', context);
    return { click, button, error, redirects };
}

// 모의 HTTP 응답 객체 생성 헬퍼
const response = status => ({
    status, ok: status >= 200 && status < 300,
    headers: { get: () => 'application/json' },
    json: async () => ({ detail: '<img src=x onerror=alert(1)>' }),
});

test('204 성공일 때 로그인 화면으로 이동하고 CSRF 헤더를 보낸다', async () => {
    const state = setup(async (url, options) => {
        assert.equal(url, '/api/logout');
        assert.equal(options.method, 'POST');
        assert.equal(options.headers['X-Requested-With'], 'XMLHttpRequest');
        return response(204);
    });
    await state.click();
    assert.deepEqual(state.redirects, ['/login']);
    assert.equal(state.error.style.display, 'none');
});

for (const status of [200, 401, 403, 500]) {
    test(`${status} 응답은 이동 없이 실패를 알리고 다시 누를 수 있다`, async () => {
        const state = setup(async () => response(status));
        await state.click();
        assert.deepEqual(state.redirects, []);
        assert.equal(state.error.style.display, 'flex');
        assert.match(state.error.textContent, /로그아웃에 실패/);
        // 에러 메시지에 HTML 태그가 해석되지 않음을 확인 (XSS 방어)
        assert.equal(state.error.textContent.includes('<img'), false);
        assert.equal(state.button.disabled, false);
    });
}

test('네트워크 실패 후 재시도하면 성공하며 대기 중 중복 요청을 막는다', async () => {
    let calls = 0;
    let release;
    const state = setup(async () => {
        calls++;
        if (calls === 1) throw new Error('offline');
        return new Promise(resolve => { release = () => resolve(response(204)); });
    });
    // 1차 시도: 오프라인 에러 발생
    await state.click();
    assert.equal(state.button.disabled, false);
    assert.deepEqual(state.redirects, []);

    // 2차 시도: 지연 응답 중 중복 클릭
    const pending = state.click();
    await state.click(); // 중복 클릭 시도
    assert.equal(calls, 2); // 추가 fetch가 호출되지 않아야 함
    assert.equal(state.button.disabled, true); // 버튼 비활성화 상태 확인
    release(); // 비동기 응답 완료
    await pending;
    assert.deepEqual(state.redirects, ['/login']);
    assert.equal(state.error.style.display, 'none');
});
