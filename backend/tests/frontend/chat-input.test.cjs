const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');

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
    vm.runInContext(readFileSync(resolve(__dirname, '../../app/static/js/chat.js'), 'utf8'), context);
    ready();
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
    state.handlers.compositionstart();
    assert.equal(state.key(), false);
    assert.equal(state.submits, 0);
    state.handlers.compositionend();
    // compositionend가 먼저 오는 브라우저의 229 이벤트도 제외한다.
    assert.equal(state.key({ keyCode: 229 }), false);
    state.key();
    assert.equal(state.submits, 1);
});

test('공백만 있는 입력은 Enter로 전송할 수 없다', () => {
    const state = setup('   ');
    state.key();
    assert.equal(state.submits, 0);
});
