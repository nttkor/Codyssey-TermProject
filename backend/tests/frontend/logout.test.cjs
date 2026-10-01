// 의존성 설치 없이 실행: node --test tests/frontend/*.test.cjs
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');

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
    vm.runInContext(readFileSync(resolve(__dirname, '../../app/static/js/common.js'), 'utf8'), context);
    vm.runInContext('initNavbar()', context);
    return { click, button, error, redirects };
}

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
    await state.click();
    assert.equal(state.button.disabled, false);
    assert.deepEqual(state.redirects, []);
    const pending = state.click();
    await state.click();
    assert.equal(calls, 2);
    assert.equal(state.button.disabled, true);
    release();
    await pending;
    assert.deepEqual(state.redirects, ['/login']);
    assert.equal(state.error.style.display, 'none');
});
