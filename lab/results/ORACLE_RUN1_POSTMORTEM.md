# Propagation Oracle Test — Run #1 Post-Mortem

**Run:** GitHub Actions run ID **39391319633** ("Propagation Oracle Test ($0)" #1)
**Design at the time:** 2 sites (Ireland, Australia) × 2 bands (14074 + 7074 kHz
USB), prediction first, 4 simultaneous recordings, stride-decoder scoring,
plain `git push` commit-back.

## What run #1 actually showed (from its job log)

| Item | Result |
|---|---|
| Prediction (sealed before recording) | Ireland → **20m**, Australia → **40m** |
| Ireland measured | 20m = **74** unique, 40m = **78** unique → **oracle WRONG** (margin 4) |
| Australia measured | Receiver `22537.proxy.kiwisdr.com` **TIMED OUT (exit 124)** in the parallel attempt **and** in the sequential fallback → **0 bytes** recorded → **INDETERMINATE** |
| Commit-back | `git push` **rejected** (remote had newer commits — a race with work pushed during the run) → step failed → **`oracle_ci.log` never reached the repo**; the scorecard survived only in the job log |

Measurement caveat: run #1's counts (74 / 78) came from the OLD 2 s-stride
decoder. Per the 2026-10-20 audit, stride counts are unique *texts* merged
across slots, not unique (slot, text) transmissions, so they are not
directly comparable with counts from later runs, which use the UTC-slot-
aligned decoder (`lab/ft8_slot_decode.py`).

## Lessons and the fixes applied (this commit)

1. **Commit-back race lost the results.**
   The commit-back step now does `git fetch origin main` + rebase onto the
   fetched main tip before pushing, and retries the fetch/rebase/push
   cycle up to **3 times**. If all attempts fail, the step emits a warning
   (not a job failure) and echoes the **full `oracle_ci.log`** into the job
   log as a last-resort record — a git race can no longer silently eat a
   completed measurement.

2. **One slow proxy receiver = one whole site lost.**
   Australia hung past the 150 s guard in both attempts, leaving the site
   INDETERMINATE. Fixes: the per-combo timeout guard is raised to **180 s**,
   and the design is extended from 2 sites to **4 sites** (adding Canada —
   `bachner.proxy.kiwisdr.com`, London, Ontario; and USA —
   `dxcentral.proxy.kiwisdr.com`, Mandeville, Louisiana), so a single dead
   receiver degrades the run instead of halving it. Predictions are now
   sealed for all 4 sites.

3. **Scoring now covers every site, honestly.**
   `oracle_score.py` scores all 4 sites; any site with a missing band or
   missing recordings is **INDETERMINATE** (never zero-filled), and the
   OVERALL line aggregates CORRECT / WRONG / TIE / INDETERMINATE **of 4**.
   All counts come from the slot-aligned decoder
   (`lab/ft8_slot_decode.py`), not the retired stride method.

## What run #1 did prove

The protocol executed end-to-end in the intended order (predict → measure →
score) and the oracle was genuinely at risk: it called Ireland for 20m and
the band it rejected won by 4 unique decodes. A falsifiable oracle that is
sometimes WRONG is the design working as intended — the failure modes worth
fixing were in the plumbing (git race, single fragile receiver), and those
are what this commit changes.
