#!/usr/bin/env node
/*
 * Nature-Mirror Mesh — DOM regression test for the app page script.
 *
 * Regression target (v0.1.1 device failure, root cause confirmed by
 * the user's on-device report + code inspection): the page used to
 * rebuild #app's innerHTML every 2.5 s unconditionally, erasing
 * whatever the user was typing into the login word fields — word 1
 * vanished before word 2 could be typed.
 *
 * This harness loads the REAL served page (passed as argv[2]),
 * extracts its <script>, and runs it in Node's vm against a minimal
 * stub DOM — just enough to execute the page's own stateSig /
 * captureInputs / restoreInputs / userIsTyping / render logic for
 * real. It then simulates a user typing and asserts:
 *
 *   1. an unchanged-state poll tick does NOT rebuild the DOM;
 *   2. a changed-state tick while a text field is focused does NOT
 *      rebuild the DOM (typing guard);
 *   3. after blur, the rebuild happens AND the typed values survive
 *      it (capture/restore);
 *   4. a logged_out→logged_in transition renders immediately even
 *      while a field is focused, and the account panel shows the
 *      auto-created words + full ID.
 *
 * Exit 0 + "UI-DOM: PASS" on success, 1 otherwise.
 */
'use strict';
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(process.argv[2], 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('UI-DOM: FAIL — no <script> in page'); process.exit(1); }
const script = m[1];

/* ---------------- minimal stub DOM ---------------- */
class El {
  constructor(id, tag) {
    this.id = id || '';
    this.tagName = (tag || 'DIV').toUpperCase();
    this.value = '';
    this.textContent = '';
    this.style = {};
    this.disabled = false;
    this.selectionStart = null;
    this.selectionEnd = null;
  }
  focus() { documentStub.activeElement = this; }
  select() {}
  setSelectionRange(a, b) { this.selectionStart = a; this.selectionEnd = b; }
}

let appInputs = [];           // input Els currently "inside" #app
let htmlSets = 0;             // how often #app.innerHTML was assigned
let currentHTML = '';
const appEl = new El('app', 'DIV');
Object.defineProperty(appEl, 'innerHTML', {
  get() { return currentHTML; },
  set(v) {
    htmlSets++;
    currentHTML = v;
    // A real browser destroys the old elements and parses new ones;
    // rebuild the input registry from the new markup (fresh Els with
    // empty values — only the page's restore step can save typing).
    appInputs = [];
    const re = /<input[^>]*>/g;
    let mm;
    while ((mm = re.exec(v)) !== null) {
      const tag = mm[0];
      const idm = tag.match(/\bid="([^"]+)"/);
      if (!idm) continue;
      const el = new El(idm[1], 'INPUT');
      const vm2 = tag.match(/\bvalue="([^"]*)"/);
      if (vm2) el.value = vm2[1];   // a parsed element starts with its value attribute
      appInputs.push(el);
    }
  },
});
appEl.contains = (el) => appInputs.includes(el) || el === appEl;

const statusEl = new El('status', 'DIV');
const errEl = new El('err', 'DIV');
const busyEl = new El('busy', 'DIV');

const documentStub = {
  activeElement: null,
  getElementById(id) {
    if (id === 'app') return appEl;
    if (id === 'status') return statusEl;
    if (id === 'err') return errEl;
    if (id === 'busy') return busyEl;
    return appInputs.find((e) => e.id === id) || null;
  },
  querySelectorAll(sel) {
    if (sel.includes('#app')) return appInputs.slice();
    return [];
  },
  execCommand() { return true; },
};

/* ---------------- fetch stub (the app's API) ---------------- */
let fetchState = { logged_in: false, postoffice_file: true,
                   contacts: [], inbox: [], sent: [] };
let fetchHealth = { postoffice: 'connected', logged_in: false };

const sandbox = {
  document: documentStub,
  navigator: {},
  console,
  setInterval: () => 0,
  setTimeout: () => 0,
  fetch: (url) => {
    const data = url.includes('/api/health') ? fetchHealth : fetchState;
    return Promise.resolve({
      json: async () => JSON.parse(JSON.stringify(data)),
    });
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

/* ---------------- the simulation ---------------- */
(async () => {
  const fails = [];
  const check = (name, cond) => {
    console.log((cond ? 'ok   ' : 'FAIL ') + name);
    if (!cond) fails.push(name);
  };
  try {
    vm.runInContext(
      script + '\n;globalThis.__x = { refresh, render };', sandbox);
    const X = sandbox.__x;
    await new Promise((r) => setImmediate(r));  // let load-time calls settle
    await X.refresh();

    check('login form rendered (w1 + w2 inputs exist)',
          !!documentStub.getElementById('w1') &&
          !!documentStub.getElementById('w2'));
    const setsAfterFirstRender = htmlSets;

    // The user types word 1, then starts word 2.
    const w1 = documentStub.getElementById('w1');
    w1.focus(); w1.value = 'apple';
    const w2 = documentStub.getElementById('w2');
    w2.focus(); w2.value = 'riv';

    await X.refresh();  // poll tick, state unchanged
    check('unchanged-state tick does not rebuild the DOM',
          htmlSets === setsAfterFirstRender);
    check('typed values intact after the tick',
          documentStub.getElementById('w1').value === 'apple' &&
          documentStub.getElementById('w2').value === 'riv');

    // State changes underneath (post office file flag flips) while
    // the user is still typing in w2: still no rebuild.
    fetchState = Object.assign({}, fetchState, { postoffice_file: false });
    await X.refresh();
    check('changed-state tick while typing does not rebuild the DOM',
          htmlSets === setsAfterFirstRender);
    check('typed values still intact',
          documentStub.getElementById('w2').value === 'riv');

    // User leaves the field; the next tick rebuilds — and the typed
    // values must survive via capture/restore.
    documentStub.activeElement = null;
    await X.refresh();
    check('rebuild happens once the user is not typing',
          htmlSets > setsAfterFirstRender);
    check('typed values preserved across the rebuild',
          documentStub.getElementById('w1').value === 'apple' &&
          documentStub.getElementById('w2').value === 'riv');

    // Login transition must render immediately, even mid-typing.
    documentStub.getElementById('w2').focus();
    fetchState = { logged_in: true,
                   id: 'abcdef0123456789abcdef0123456789',
                   short_id: 'abcdef0123456789',
                   words: ['apple', 'river'],
                   postoffice_file: true,
                   backend: { pn_path: true },
                   contacts: [], inbox: [], sent: [] };
    fetchHealth = { postoffice: 'connected', logged_in: true,
                    backend_ready: true, backend: { pn_path: true } };
    await X.refresh();
    check('login transition renders immediately while focused',
          !!documentStub.getElementById('aw1'));
    check('account panel shows the 2 words',
          documentStub.getElementById('aw1').value === 'apple' &&
          documentStub.getElementById('aw2').value === 'river');
    check('account panel shows the full 32-hex ID',
          documentStub.getElementById('aid').value ===
            'abcdef0123456789abcdef0123456789');
  } catch (e) {
    check('simulation ran without exception (' + e.message + ')', false);
  }
  console.log(fails.length ? `UI-DOM: FAIL (${fails.length} checks)`
                           : 'UI-DOM: PASS');
  process.exit(fails.length ? 1 : 0);
})();
