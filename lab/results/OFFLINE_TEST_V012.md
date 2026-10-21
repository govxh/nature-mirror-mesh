# No-Internet Acceptance Test — v0.1.2 (auto-create + typing fix)

Date (UTC): 2026-10-21 — suite started 04:22 UTC inside the namespace.
Question put to the test: **does the v0.1.2 app — including the new
one-tap auto-create flow — still need the internet at all?**
Answer: **No.** The full four-run acceptance suite (manual flow +
auto flow, each in subprocess and thread backend modes) passed
inside a network environment where internet access was not merely
unused but *impossible* — no interface except loopback, no routes
at all. Suite exit code: **0**.

## Isolation method (kernel-enforced, strongest available)

Identical recipe to the original OFFLINE_TEST.md: the entire suite
ran inside a **fresh Linux network namespace** created with
`unshare -rn` (user + network namespaces). Inside it:

- the **only** interface was `lo` (loopback), brought up with
  `ip link set lo up`;
- the route table was **completely empty**;
- all proxy endpoint environment variables (`http_proxy`,
  `https_proxy`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`,
  `all_proxy`) were **unset** before the test;
- the suite ran against **byte-identical copies** of
  `app/nmm_app.py`, `app/postoffice.py`, `app/test_app_flow.py` and
  `app/test_ui_dom.js` in a scratch dir (`/tmp/nmm_offline_012/`;
  nmm_app.py copy sha256 verified identical to the project's), so
  the host-run evidence files were not overwritten.

### Isolation evidence (captured inside, before the suite)

From the raw combined log `lab/results/offline_test_v012.log`:

- `curl https://example.com` → exit 6 (could not resolve host)
- `curl http://1.1.1.1` → exit 7 (could not connect)
- `ping -c 1 -W 2 8.8.8.8` → exit 2 (network unreachable)
- `getent hosts example.com` → exit 2 (no DNS)
- raw Python TCP connect to 93.184.216.34:443 →
  `OSError [Errno 101] Network is unreachable`

## Results — all four runs, pre-registered criteria

Criteria per run are those of `lab/results/APP_TEST.md` (manual:
(i) deterministic IDs, (ii) offline delivery, (iii) reply, (ui)
typing-preservation DOM test — the DOM test also ran *inside* the
namespace; auto: (gen) generated words deterministically derive the
session ID, (relogin) manual login with the generated words
reproduces it, (deliver) offline delivery between two auto-created
accounts, (reply) reply delivered; every send “stored at post
office”).

| Run | Stamp | Verdict |
|---|---|---|
| Manual / subprocess | 20261021-042216 | **PASS** |
| Manual / thread (`NMM_THREAD_BACKEND=1`) | 20261021-042245 | **PASS** |
| Auto / subprocess | 20261021-042306 | **PASS** |
| Auto / thread (`NMM_THREAD_BACKEND=1`) | 20261021-042332 | **PASS** |

Per-run raw logs: `lab/results/offline_test_v012_subprocess.log`,
`offline_test_v012_thread.log`, `offline_test_v012_auto.log`,
`offline_test_v012_auto_thread.log`; combined raw log including the
isolation evidence: `lab/results/offline_test_v012.log`.

Deterministic IDs reproduced again with zero internet:
“apple river” → `118624df2e583c1bcaeca341dc813ab3`,
“tiger moon” → `f543ccb8a691f98edb0eb68e5d428940`.

Everything the app used was loopback on this one machine: the web
UI at 127.0.0.1:8899 and the post office's Reticulum TCP interface
at 127.0.0.1:4429 — and, new in v0.1.2, the on-device identity
directory (`data/identities/`), which is plain local files.

## Honest scope

Proven: the v0.1.2 app software — manual and auto account
creation, deterministic IDs, post-office store-and-forward,
replies, the health endpoint, and the typing-safe page — runs
end-to-end with internet access made impossible, in both backend
modes. Not proven here (unchanged from before): anything about
distance, radio, or real-device behaviour — the v0.1.2 device
retest on the user's phone remains the acceptance gate for the UX
fixes.
