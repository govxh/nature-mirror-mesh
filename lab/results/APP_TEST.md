# App Acceptance Test — Nature-Mirror Mesh tiny app (v1)

Date (UTC): 2026-10-20 12:04

The user's own 5-step acceptance flow, executed against the
real app processes (postoffice.py + nmm_app.py) over their
HTTP endpoints — TWICE, once per backend mode:

- **Subprocess mode** (default): one backend process per
  login, spawned via sys.executable — the VM/Termux path.
  Full log: `app/test_app_flow.log`.
- **Thread mode** (`NMM_THREAD_BACKEND=1`): the per-login
  backend runs on a daemon thread inside the web process —
  the Android/Chaquopy path, where an APK contains no
  standalone Python executable to spawn. The post office
  remains a separate process in both runs. Full log:
  `app/test_app_flow_thread.log`.

## Pre-registered criteria

PASS requires, in EACH of the two modes:

- (i) same 2 words → same ID on re-login (both accounts);
- (ii) account 1 receives account 2's exact message after
  being offline while it was sent;
- (iii) account 2 receives the exact reply;
- each send reaches status “stored at post office” at the
  sender, and account 1's local inbox file does not contain
  the token before step 4.

## Run 1 — default subprocess mode

Run stamp: 20261020-120057

| Step | What | Result | Evidence |
|---|---|---|---|
| 1 | create account 1 ('apple river') | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (deterministic expectation 118624df2e583c1bcaeca341dc813ab3) |
| 2 | clear data → account 2 ('tiger moon'), different ID | ✅ PASS | logged_out=True http=200 id=f543ccb8a691f98edb0eb68e5d428940 |
| 3 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=2f0cbffc4a86 status='stored at post office' spool_files=1 token_in_acct1_local_inbox=False |
| 4a | re-login account 1 with only its 2 words → same ID | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (original 118624df2e583c1bcaeca341dc813ab3) |
| 4b | account 1 receives account 2's exact message | ✅ PASS | content match=True token=NMM-APPTEST-20261020-120057-ONE |
| 5 | account 1 replies; account 2 (re-login, same ID) receives the exact reply | ✅ PASS | reply_status='stored at post office' id2_again=f543ccb8a691f98edb0eb68e5d428940 (same=True) reply_received=True token=NMM-APPTEST-20261020-120057-TWO |

- (i) same 2 words → same ID on re-login (both accounts): **True**
- (ii) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum account 1, this waited at the post office: NMM-APPTEST-20261020-120057-ONE”
- (iii) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam account 2, reply from account 1: NMM-APPTEST-20261020-120057-TWO”

Run verdict: **PASS**

## Run 2 — thread mode (NMM_THREAD_BACKEND=1)

Run stamp: 20261020-120123

| Step | What | Result | Evidence |
|---|---|---|---|
| 1 | create account 1 ('apple river') | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (deterministic expectation 118624df2e583c1bcaeca341dc813ab3) |
| 2 | clear data → account 2 ('tiger moon'), different ID | ✅ PASS | logged_out=True http=200 id=f543ccb8a691f98edb0eb68e5d428940 |
| 3 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=c0ec3f3ce831 status='stored at post office' spool_files=1 token_in_acct1_local_inbox=False |
| 4a | re-login account 1 with only its 2 words → same ID | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (original 118624df2e583c1bcaeca341dc813ab3) |
| 4b | account 1 receives account 2's exact message | ✅ PASS | content match=True token=NMM-APPTEST-20261020-120123-ONE |
| 5 | account 1 replies; account 2 (re-login, same ID) receives the exact reply | ✅ PASS | reply_status='stored at post office' id2_again=f543ccb8a691f98edb0eb68e5d428940 (same=True) reply_received=True token=NMM-APPTEST-20261020-120123-TWO |

- (i) same 2 words → same ID on re-login (both accounts): **True**
- (ii) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum account 1, this waited at the post office: NMM-APPTEST-20261020-120123-ONE”
- (iii) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam account 2, reply from account 1: NMM-APPTEST-20261020-120123-TWO”

Run verdict: **PASS**

## Verdict: PASS — both modes

## Honest scope
Single device, loopback TCP only — the post office and both
accounts ran on one machine, exactly like the user's one-phone
test will. No internet, no radio. Thread mode shares one
process-wide Reticulum instance across logins (RNS allows
only one per process) and the backend deregisters its LXMF
destinations (delivery + the router's propagation
destination) at logout so the same account can log in
again; this mirrors the in-APK lifecycle but is verified
on the VM only — in-APK behaviour on a real Android device
remains unverified until a device run. The 2-word key is a
testing convenience and is cryptographically weak by design
at this stage (documented in app/README.md).
