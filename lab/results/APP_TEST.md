# App Acceptance Test — Nature-Mirror Mesh tiny app (v1)

Date (UTC): 2026-10-20 11:15

The user's own 5-step acceptance flow, executed against the
real app processes (postoffice.py + nmm_app.py + per-login
backends) over their HTTP endpoints. Full log:
`app/test_app_flow.log`.

## Flow

| Step | What | Result | Evidence |
|---|---|---|---|
| 1 | create account 1 ('apple river') | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (deterministic expectation 118624df2e583c1bcaeca341dc813ab3) |
| 2 | clear data → account 2 ('tiger moon'), different ID | ✅ PASS | logged_out=True http=200 id=f543ccb8a691f98edb0eb68e5d428940 |
| 3 | account 2 sends to account 1's ID; message stored at post office | ✅ PASS | local_id=7a8cbd2c3b4c status='stored at post office' spool_files=1 token_in_acct1_local_inbox=False |
| 4a | re-login account 1 with only its 2 words → same ID | ✅ PASS | http=200 id=118624df2e583c1bcaeca341dc813ab3 (original 118624df2e583c1bcaeca341dc813ab3) |
| 4b | account 1 receives account 2's exact message | ✅ PASS | content match=True token=NMM-APPTEST-20261020-111440-ONE |
| 5 | account 1 replies; account 2 (re-login, same ID) receives the exact reply | ✅ PASS | reply_status='stored at post office' id2_again=f543ccb8a691f98edb0eb68e5d428940 (same=True) reply_received=True token=NMM-APPTEST-20261020-111440-TWO |

## Pre-registered criteria

- (i) same 2 words → same ID on re-login (both accounts): **True**
- (ii) account 1 receives account 2's exact message after being offline: **True** — message sent: “Assalam-o-Alaikum account 1, this waited at the post office: NMM-APPTEST-20261020-111440-ONE”
- (iii) account 2 receives the exact reply: **True** — reply sent: “Wa-Alaikum-Assalam account 2, reply from account 1: NMM-APPTEST-20261020-111440-TWO”

## Verdict: PASS

## Honest scope
Single device, loopback TCP only — the post office and both
accounts ran on one machine, exactly like the user's one-phone
test will. No internet, no radio. The 2-word key is a testing
convenience and is cryptographically weak by design at this
stage (documented in app/README.md).
