# App Acceptance Test — Nature-Mirror Mesh tiny app

Date (UTC): 2026-10-21 04:21

## v0.1.2 — what changed and why

v0.1.1 reached a real phone and the user reported: “it
doesn't let me write anything” — the login screen showed two
empty word fields and typing into them failed.

**Root cause (confirmed by the user's on-device report and
by code inspection):** the page ran `refresh()` on a 2.5 s
interval and `render()` rebuilt the whole `#app` innerHTML
on every tick, erasing in-progress typing — the user typed
word 1, the tick fired, word 1 vanished before word 2.
Secondary risks fixed at the same time: the WebView was not
explicitly focusable-in-touch-mode (some devices then never
raise the keyboard for page inputs), and every API failure
was silent (a dead “Loading…” screen with no reason shown).

Fixes in v0.1.2:

- **Re-rendering can no longer destroy typing.** A rebuild
  happens only when the rendered state actually changed
  (signature compare); it never happens while a text field
  is focused, unless the login state itself flipped; and
  when it does happen, every input's value + focus +
  selection are captured first and restored after.
  Regression-tested by executing the real served page in a
  stub DOM (`app/test_ui_dom.js`, step U in runs 1–2): the
  same test FAILS against the v0.1.1 page (typing wiped on
  the first tick) and must PASS here.
- **One-tap account creation.** “Create account” needs no
  typing: the backend generates 2 random words (`secrets`
  over an embedded 256-word list), logs in through the
  exact same identity derivation as manual entry, and the
  “Your account” panel shows the 2 words and the full
  32-hex ID in readonly fields with Copy buttons, plus:
  “Save these 2 words — they are your only key. Anyone
  with them has your account.” Manual 2-word entry stays
  below for returning users.
- **No more silent failures.** Every API call surfaces its
  error in a visible error line; login shows a busy state;
  a status line polls `GET /api/health` (post office
  reachable? backend stage? session state?) built on the
  existing ready.json / status.json IPC.
- **WebView hardening (Android shell):** focusable +
  focusable-in-touch-mode + requestFocus on load, and a
  WebChromeClient. Cleartext config and permissions
  unchanged.
- **Reliability fix found BY these tests** (first suite
  attempt: 2 of 4 runs failed intermittently with “failed:
  ID not found (no path)”): a sender waited for a *live
  path* to the offline recipient, but RNS culls a path-table
  entry the moment the interface it was learned on
  disappears — and an offline contact's only interface is
  its own closed connection (post office log, instrumented
  repro: “Ignoring path request …, no path known” for a
  destination that had announced to it directly). A
  PROPAGATED message never needed that path — only the
  recipient's public key. Now every login publishes its
  public key to an on-device identity directory
  (`data/identities/<id>.pub`) and `do_send` resolves the
  identity from there / RNS recall first; the 240 s
  path-request loop remains only as fallback for IDs never
  seen on this device. Same repro sequence after the fix:
  “stored at post office” in ~8 s.

## The runs

Four runs against the real app processes (postoffice.py +
nmm_app.py) over their HTTP endpoints — the user's 5-step
manual flow and the new auto flow, each in both backend
modes:

- **Subprocess mode** (default): one backend process per
  login, spawned via sys.executable — the VM/Termux path.
- **Thread mode** (`NMM_THREAD_BACKEND=1`): the per-login
  backend runs on a daemon thread inside the web process —
  the Android/Chaquopy path, where an APK contains no
  standalone Python executable to spawn. The post office
  remains a separate process in both runs.

Full logs: `app/test_app_flow.log`,
`app/test_app_flow_thread.log`, `app/test_app_flow_auto.log`,
`app/test_app_flow_auto_thread.log`. The offline (loopback-
only network namespace) rerun of this suite is reported in
`lab/results/OFFLINE_TEST_V012.md`.

## Pre-registered criteria

PASS requires, in EACH mode:

- Manual: (i) same 2 words → same ID on re-login (both
  accounts); (ii) account 1 receives account 2's exact
  message after being offline while it was sent; (iii)
  account 2 receives the exact reply; (ui) the typing-
  preservation DOM regression test passes; each send
  reaches “stored at post office”, and account 1's local
  inbox file does not contain the token before step 4.
- Auto: (gen) auto-create's words deterministically derive
  the session ID and state shows them; (relogin) manual
  login with the generated words reproduces the ID;
  (deliver) offline delivery between two auto-created
  accounts; (reply) the reply is delivered.

## Run 1 — manual flow, subprocess mode

Run stamp: 20261021-041957

| Step | What | Result | Evidence |
|---|---|---|---|
| U | served page: typing never wiped by re-render (DOM regression test) | ✅ PASS | structural assertions passed; DOM simulation: ok   login form rendered (w1 + w2 inputs exist); ok   unchanged-state tick does not rebuild the DOM; ok   typed values intact after the tick; ok   changed-state tick while typing does not rebuild the DOM; ok   typed values still intact; ok   rebuild happens once the user is not typing; ok   typed values preserved across the rebuild; ok   login transition renders immediately while focused; ok   account panel shows the 2 words; ok   account panel shows the full 32-hex ID; UI-DOM: PASS |
| 1 | create account 1 ('apple river') | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (deterministic expectation 118624df2e583c1bcaeca341dc813ab3) |
| 2 | clear data → account 2 ('tiger moon'), different ID | ✅ PASS | logged_out=True http=200 id=f543ccb8a691f98edb0eb68e5d428940 |
| 3 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=c6d76cc44a3b status='stored at post office' spool_files=1 token_in_acct1_local_inbox=False |
| 4a | re-login account 1 with only its 2 words → same ID | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (original 118624df2e583c1bcaeca341dc813ab3) |
| 4b | account 1 receives account 2's exact message | ✅ PASS | content match=True token=NMM-APPTEST-20261021-041957-ONE |
| 5 | account 1 replies; account 2 (re-login, same ID) receives the exact reply | ✅ PASS | reply_status='stored at post office' id2_again=f543ccb8a691f98edb0eb68e5d428940 (same=True) reply_received=True token=NMM-APPTEST-20261021-041957-TWO |

- (i) same 2 words → same ID on re-login (both accounts): **True**
- (ii) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum account 1, this waited at the post office: NMM-APPTEST-20261021-041957-ONE”
- (iii) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam account 2, reply from account 1: NMM-APPTEST-20261021-041957-TWO”
- (ui) typing-preservation DOM regression test: **True**

Run verdict: **PASS**

## Run 2 — manual flow, thread mode (NMM_THREAD_BACKEND=1)

Run stamp: 20261021-042027

| Step | What | Result | Evidence |
|---|---|---|---|
| U | served page: typing never wiped by re-render (DOM regression test) | ✅ PASS | structural assertions passed; DOM simulation: ok   login form rendered (w1 + w2 inputs exist); ok   unchanged-state tick does not rebuild the DOM; ok   typed values intact after the tick; ok   changed-state tick while typing does not rebuild the DOM; ok   typed values still intact; ok   rebuild happens once the user is not typing; ok   typed values preserved across the rebuild; ok   login transition renders immediately while focused; ok   account panel shows the 2 words; ok   account panel shows the full 32-hex ID; UI-DOM: PASS |
| 1 | create account 1 ('apple river') | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (deterministic expectation 118624df2e583c1bcaeca341dc813ab3) |
| 2 | clear data → account 2 ('tiger moon'), different ID | ✅ PASS | logged_out=True http=200 id=f543ccb8a691f98edb0eb68e5d428940 |
| 3 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=e533bf719724 status='stored at post office' spool_files=1 token_in_acct1_local_inbox=False |
| 4a | re-login account 1 with only its 2 words → same ID | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (original 118624df2e583c1bcaeca341dc813ab3) |
| 4b | account 1 receives account 2's exact message | ✅ PASS | content match=True token=NMM-APPTEST-20261021-042027-ONE |
| 5 | account 1 replies; account 2 (re-login, same ID) receives the exact reply | ✅ PASS | reply_status='stored at post office' id2_again=f543ccb8a691f98edb0eb68e5d428940 (same=True) reply_received=True token=NMM-APPTEST-20261021-042027-TWO |

- (i) same 2 words → same ID on re-login (both accounts): **True**
- (ii) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum account 1, this waited at the post office: NMM-APPTEST-20261021-042027-ONE”
- (iii) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam account 2, reply from account 1: NMM-APPTEST-20261021-042027-TWO”
- (ui) typing-preservation DOM regression test: **True**

Run verdict: **PASS**

## Run 3 — auto flow, subprocess mode

Run stamp: 20261021-042052

| Step | What | Result | Evidence |
|---|---|---|---|
| A0 | GET /api/health: app up, post office connected | ✅ PASS | http=200 health={'app': 'up', 'postoffice': 'connected', 'postoffice_file': True, 'logged_in': False} |
| A1 | auto-create account 1 (no typing): words generated, ID = deterministic ID of the words, state shows words + ID | ✅ PASS | http=200 words=('donkey', 'coin') id=7e87793d04e5fef251c51d881bbbe470 deterministic=7e87793d04e5fef251c51d881bbbe470 state_words=('donkey', 'coin') |
| A2 | log out → manual login with the generated words → same ID | ✅ PASS | http=200 id=7e87793d04e5fef251c51d881bbbe470 (original 7e87793d04e5fef251c51d881bbbe470) |
| A3 | auto-create account 2 → different account, ID matches its generated words | ✅ PASS | words=('shark', 'tea') id=92fea31fea984c08cde97363ca94f87a deterministic=92fea31fea984c08cde97363ca94f87a tries=['92fea31fea984c08cde97363ca94f87a'] |
| A4 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=6dd5f74042d7 status='stored at post office' token_in_acct1_local_inbox=False |
| A5 | manual login with account 1's generated words → same ID, waiting message received | ✅ PASS | http=200 id=7e87793d04e5fef251c51d881bbbe470 same=True message_received=True token=NMM-AUTOTEST-20261021-042052-ONE |
| A6 | reply sent; manual login with account 2's generated words → same ID, reply received | ✅ PASS | reply_status='stored at post office' id2_again=92fea31fea984c08cde97363ca94f87a same=True reply_received=True token=NMM-AUTOTEST-20261021-042052-TWO |

- (gen) auto-create returns 2 words whose deterministic ID is the session ID, state shows the same words + ID: **True**
- (relogin) manual login with the generated words reproduces the same ID: **True**
- (deliver) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum auto account 1, this waited at the post office: NMM-AUTOTEST-20261021-042052-ONE”
- (reply) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam auto account 2, reply from auto account 1: NMM-AUTOTEST-20261021-042052-TWO”

Run verdict: **PASS**

## Run 4 — auto flow, thread mode (NMM_THREAD_BACKEND=1)

Run stamp: 20261021-042117

| Step | What | Result | Evidence |
|---|---|---|---|
| A0 | GET /api/health: app up, post office connected | ✅ PASS | http=200 health={'app': 'up', 'postoffice': 'connected', 'postoffice_file': True, 'logged_in': False} |
| A1 | auto-create account 1 (no typing): words generated, ID = deterministic ID of the words, state shows words + ID | ✅ PASS | http=200 words=('trail', 'flower') id=ef01367edf4ed1eceb442b3750c054e1 deterministic=ef01367edf4ed1eceb442b3750c054e1 state_words=('trail', 'flower') |
| A2 | log out → manual login with the generated words → same ID | ✅ PASS | http=200 id=ef01367edf4ed1eceb442b3750c054e1 (original ef01367edf4ed1eceb442b3750c054e1) |
| A3 | auto-create account 2 → different account, ID matches its generated words | ✅ PASS | words=('frost', 'wagon') id=28485c2a40abc034845bbf42744e481b deterministic=28485c2a40abc034845bbf42744e481b tries=['28485c2a40abc034845bbf42744e481b'] |
| A4 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=0b07bd78bf7e status='stored at post office' token_in_acct1_local_inbox=False |
| A5 | manual login with account 1's generated words → same ID, waiting message received | ✅ PASS | http=200 id=ef01367edf4ed1eceb442b3750c054e1 same=True message_received=True token=NMM-AUTOTEST-20261021-042117-ONE |
| A6 | reply sent; manual login with account 2's generated words → same ID, reply received | ✅ PASS | reply_status='stored at post office' id2_again=28485c2a40abc034845bbf42744e481b same=True reply_received=True token=NMM-AUTOTEST-20261021-042117-TWO |

- (gen) auto-create returns 2 words whose deterministic ID is the session ID, state shows the same words + ID: **True**
- (relogin) manual login with the generated words reproduces the same ID: **True**
- (deliver) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum auto account 1, this waited at the post office: NMM-AUTOTEST-20261021-042117-ONE”
- (reply) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam auto account 2, reply from auto account 1: NMM-AUTOTEST-20261021-042117-TWO”

Run verdict: **PASS**

## Verdict: PASS — all four runs

## Honest scope
Single device, loopback TCP only — the post office and both
accounts ran on one machine, exactly like the user's one-phone
test will. No internet, no radio. Thread mode shares one
process-wide Reticulum instance across logins (RNS allows
only one per process) and the backend deregisters its LXMF
destinations (delivery + the router's propagation
destination) at logout so the same account can log in
again; this mirrors the in-APK lifecycle but is verified
on the VM only. v0.1.2's fixes — including the typing fix —
are VM-verified against the real served page and the real
app processes; **the device retest on the user's phone is
still pending** and is the acceptance gate for the UX fix.
The 2-word key (typed or generated) is a testing
convenience and is cryptographically weak by design at
this stage (documented in app/README.md).
