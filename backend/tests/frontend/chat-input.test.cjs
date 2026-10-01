/**
 * AskMate 프론트엔드 채팅 입력창 및 키보드 이벤트 단위 테스트 (chat-input.test.cjs)
 *
 * [파일 개요]
 * 본 모듈은 Node.js `node:test`와 `node:vm`을 활용하여 브라우저 없이 가상 DOM 환경을 구축하고,
 * `chat.js`의 키보드 이벤트 리스너가 한글 IME 조합 상태(`compositionstart`, `compositionend`, `keyCode 229`),
 * Shift+Enter 줄바꿈, 및 공백 입력 방지 로직을 올바르게 제어하는지 단위 검증합니다.
 *
 * [실행 방법]
 * node --test backend/tests/frontend/*.test.cjs
 *
 * [주요 검증 항목]
 * 1. 일반 Enter 전송:
 *    - 한글 조합이 끝난 상태에서 Enter 입력 시 폼의 submit 이벤트가 정확히 1회 트리거되는지 확인.
 * 2. 한글 조합(IME) 중복 전송 방어:
 *    - `isComposing: true` 상태에서 발생한 Enter는 전송을 무시하는지 확인.
 *    - 브라우저별 IME 조합 이벤트(`keyCode === 229`) 발생 시 전송을 무시하는지 확인.
 * 3. 줄바꿈 및 공백 방어:
 *    - Shift + Enter 입력 시 폼이 제출되지 않고 줄바꿈이 유지되는지 확인.
 *    - 공백만 입력된 상태(`'   '`)에서는 Enter를 눌러도 전송되지 않는지 확인.
 */

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');

/**
 * 가상 DOM 환경을 생성하고 chat.js를 실행하여 이벤트 핸들러와 상태를 추출하는 헬퍼 함수.
 *
 * @param {string} [value='한글'] - 채팅 입력창 초기 텍스트
 * @returns {{handlers: Object, submits: number, key: Function}}
 */
function setup(value = '한글') {
    let ready;
    let submits = 0;
    const handlers = {};
    const element = () => ({
        value, disabled: false, style: {}, scrollHeight: 20,
        classList: { add() {}, remove() {} }, addEventListener() {},
    });
    const elements = Object.fromEntries([
        'chatForm', 'chatInput', 'chatSendBtn', 'chatMessages', 'charCounter',
        'chatErrorBanner', 'chatErrorText', 'chatRetryBtn', 'chatDismissErrorBtn',
    ].map(id => [id, element()]));
    elements.chatForm.dispatchEvent = () => { submits++; };
    elements.chatInput.addEventListener = (name, handler) => { handlers[name] = handler; };
    const context = vm.createContext({
        document: {
            addEventListener: (_, handler) => { ready = handler; },
            getElementById: id => elements[id], querySelectorAll: () => [],
        },
        Event: class {},
    });
    // chat.js 코드를 가상 컨텍스트에서 실행
    vm.runInContext(readFileSync(resolve(__dirname, '../../app/static/js/chat.js'), 'utf8'), context);
    ready(); // DOMContentLoaded 트리거
    return {
        handlers, get submits() { return submits; },
        key(extra = {}) {
            let prevented = false;
            handlers.keydown({
                key: 'Enter', shiftKey: false, isComposing: false, keyCode: 13,
                preventDefault: () => { prevented = true; }, ...extra,
            });
            return prevented;
        },
    };
}

test('일반 Enter는 한 번 전송한다', () => {
    const state = setup();
    assert.equal(state.key(), true);
    assert.equal(state.submits, 1);
});

for (const event of [{ isComposing: true }, { keyCode: 229 }, { shiftKey: true }]) {
    test(`조합 또는 줄바꿈 Enter는 전송하지 않는다: ${JSON.stringify(event)}`, () => {
        const state = setup();
        assert.equal(state.key(event), false);
        assert.equal(state.submits, 0);
    });
}

test('조합 상태를 추적하며 조합 종료 후 일반 Enter만 전송한다', () => {
    const state = setup();
    // 1. 자모 조합 시작 시 Enter 차단 확인
    state.handlers.compositionstart();
    assert.equal(state.key(), false);
    assert.equal(state.submits, 0);

    // 2. 자모 조합 종료
    state.handlers.compositionend();
    // compositionend가 먼저 오는 브라우저의 229 이벤트도 제외 확인
    assert.equal(state.key({ keyCode: 229 }), false);

    // 3. 조합 완료 후 일반 Enter 입력 시 정상 전송 확인
    state.key();
    assert.equal(state.submits, 1);
});

test('공백만 있는 입력은 Enter로 전송할 수 없다', () => {
    const state = setup('   ');
    state.key();
    assert.equal(state.submits, 0);
});
