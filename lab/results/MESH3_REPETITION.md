# Mesh3 Repetition — Claim 2 Remedy (EVIDENCE_REVIEW)
**Date:** 2026-10-20 · **Machine:** sandbox VM (TCP loopback only; **no radio transmission was made or claimed**) · Budget: $0

## Why this exists
`lab/results/EVIDENCE_REVIEW.md` graded **Claim 2 — "3-node LXMF routed mesh (S → T → C) forwards correctly" — LOW**: the post-fix evidence was a single canonical PASS (n=1) after documented intermittent failures (2 FAIL runs with `[S] TIMEOUT: no path to C`, root-caused to 0.5 s `request_path()` hammering + short node head-starts; fixed in `lxmf_mesh3_test.py`, see RESULTS2.md Task 2). The prescribed remedy was repetition: replace the anecdote with a measured pass rate.

## Protocol (pre-registered before the runs)
- Harness: `lab/mesh3_repeat.py` — runs the **unchanged** `lab/lxmf_mesh3_test.py` N times sequentially; each run is an independent 3-process mesh with a fresh unique token; per-run timeout 120 s; the harness records every run's exit code, token, RESULT line and failure-mode line, and **never stops at the first failure** (the failure rate is the datum). Between runs it sweeps orphaned test processes and waits for the test's fixed ports (51721/51722) to refuse connections, so TIME_WAIT sockets cannot poison the next run.
- **Success criterion, fixed in advance** (also stated in the wrapper header): **≥ 8/10 PASS (≥ 80%) ⇒ 3-node transport forwarding is considered reliable** and Claim 2 may be upgraded. Below 8/10, Claim 2 stays LOW and the recorded failure modes carry the conclusion instead.
- The identical wrapper runs in CI via `.github/workflows/mesh3.yml` ("Mesh3 Repetition ($0 CI)") so the local and CI code paths are the same.

## Local results — Attempt 1 (the only attempt; no re-run was needed)
**10/10 PASS** · total wall time 260.9 s · all exits 0 · failure modes: none.
Full record (summary header + every run's complete output): `lab/results/mesh3_repeat_local.log`.

| Run | Token | Exit | Wall (s) | Result | Failure mode |
|---|---|---|---|---|---|
| 1 | `NMM-MESH3-20261020-092408` | 0 | 19.4 | PASS | — |
| 2 | `NMM-MESH3-20261020-092429` | 0 | 19.3 | PASS | — |
| 3 | `NMM-MESH3-20261020-092449` | 0 | 76.4 | PASS | — |
| 4 | `NMM-MESH3-20261020-092607` | 0 | 19.3 | PASS | — |
| 5 | `NMM-MESH3-20261020-092627` | 0 | 19.5 | PASS | — |
| 6 | `NMM-MESH3-20261020-092647` | 0 | 19.5 | PASS | — |
| 7 | `NMM-MESH3-20261020-092708` | 0 | 19.4 | PASS | — |
| 8 | `NMM-MESH3-20261020-092728` | 0 | 19.3 | PASS | — |
| 9 | `NMM-MESH3-20261020-092749` | 0 | 19.3 | PASS | — |
| 10 | `NMM-MESH3-20261020-092809` | 0 | 19.3 | PASS | — |

## Observations
- 9 of 10 runs completed in 19.3–19.5 s. Run 3 took 76.4 s — still a clean PASS (paths are token-verified, `hops_to(C)=2` at S), but it shows a real slow tail in path discovery/announce propagation even when delivery ultimately succeeds. Latency varies; delivery, in this sample, did not fail.
- No port-reuse/TIME_WAIT failures occurred: the harness's sweep + port-free wait between runs kept the fixed ports (51721/51722) clean across all 10 sequential runs.
- The pre-fix failure mode (`[S] TIMEOUT: no path to C`) did not recur once in 10 runs — consistent with the RESULTS2 root-cause story (5 s path-request spacing + longer head-starts), now backed by repetition instead of a single canonical run.

## What this does to Claim 2's grade
- **The pre-registered criterion is MET: 10/10 PASS ≥ 8/10.** The n=1 objection in EVIDENCE_REVIEW is answered: locally, the fixed test is 10-for-10 with token-exact, hop-proven delivery.
- Supported conclusion: **Claim 2 upgrades from LOW to MODERATE** on this evidence — reliability is now measured (n=10, 100%, zero recurrences of the old failure mode), not anecdotal.
- What still caps it below HIGH: (a) all 10 runs are on one machine over TCP loopback — the same indirectness caveat as the rest of the lab (loopback stands in for a future radio link; no radio path is proven); (b) independent-machine replication is still pending. The CI twin of this exact harness (`.github/workflows/mesh3.yml`, artifact = the repetition log) is the queued confirmation: a ≥ 8/10 CI result on GitHub's runners would make HIGH arguable for the loopback-scoped claim.
- No second attempt was run or needed: Attempt 1 is the complete record, preserved verbatim in `lab/results/mesh3_repeat_local.log` (and `mesh3_repeat_last.log`).
