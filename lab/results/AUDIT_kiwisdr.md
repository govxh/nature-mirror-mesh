# AUDIT — KiwiSDR FT8 reception claim (GitHub Actions run 39389957321)
**Date:** 2026-10-20 · **Auditor:** independent re-analysis from the raw artifact, not from the Actions status.
**Rule applied:** a green Actions checkmark is not evidence. Every claim below was re-derived from the
downloaded artifact bytes, the decoder source code, and fresh decoder runs. **$0 spent; receive-only; no radio transmission.**

## 1. Artifact identity & preservation
- Artifact under audit: `kiwisdr-reception` from run **39389957321** (workflow "KiwiSDR Live FT8 Reception ($0)").
- Downloaded zip SHA-256: `554ba4d9f0ce0487ddb8500ef25520e78b645091e7c0dc84699fc3038b6b4fac`
  — **identical to the digest GitHub lists for the artifact.** The bytes audited are the bytes CI produced.
- An untouched copy is preserved at `lab/audit/kiwisdr-reception_run39389957321.zip`; analysis used a separate extracted working copy.
- Contents (2 files):
  | File | Bytes |
  |---|---|
  | `kiwisdr_recording.wav` | 2,166,828 |
  | `lab/results/kiwisdr_ci.log` | 31,473 |
- The repo-committed `lab/results/kiwisdr_ci.log` (fetched from the public raw URL) is **byte-identical**
  to the artifact's log (both SHA-256 `a422fb7f64dc95df05b9428fb3a0b6dc15bdaa7be2955c93a674339893e81c4a`).
- WAV SHA-256: `0bc50084a9e0c2457044c6c59e8384aa549d5ca31125d82e65e028f90323b034`.

## 2. The claim being audited
`kiwisdr_ci.log` states: on 2026-10-20, starting 07:57:25 UTC, a GitHub runner recorded 90 s of live audio from the
public KiwiSDR **emeraldsdr.ddns.net:8073 (Carlow, Ireland)** at **14074 kHz USB** (passband 200–3000 Hz) via
kiwirecorder, then decoded FT8 with ft8_lib by slicing the WAV into 38 windows of 15 s at a 2 s stride:
**180 decode events, 58 unique message texts.**

## 3. WAV authenticity — is the audio genuinely off-air?
Header: **12000 Hz, mono, 16-bit, 1,083,392 samples, 2,166,784 data bytes, 90.2827 s** — exactly the log's claims
(2,166,828 file = 44-byte header + data; the log's own "Produced WAV … (2166828 bytes)" matches the artifact byte count).

Measured evidence (numpy/scipy STFT analysis of the artifact WAV itself):
| Test | Result | What it rules out |
|---|---|---|
| Exact-zero samples | 105 of 1,083,392 (0.0097%) | Digital silence / padded placeholder (would show long zero runs) |
| Longest run of identical samples | 2 samples (0.2 ms) | Frozen or looped synthetic buffers |
| Clipped samples | 0; peak 15,536 of 32,767; DC offset 0.53 | Overdriven or normalized-to-full-scale synthetic audio |
| Per-second RMS | 1,856 → 7,488 (CV 0.24) | Constant-level generated audio; shows live band/AGC dynamics |
| Exact duplicate 1-s chunks | 0 of 90 | Looping a short segment to fake 90 s |
| Band noise floor over time | varies 82× (median power 134 → 1.1×10⁴) | Fixed synthetic noise floor |
| Simultaneous tone tracks, busiest slot | **14 distinct tracks** (slot-averaged spectrum, ≥6 dB over floor); **18–24 simultaneous peaks** at single instants | A synthetic 1-signal file (gen_ft8 output shows exactly 1 track) |
| Burst gating vs 15 s grid | best-fit grid contrast **+0.611** — energy is strongly gated on the FT8 15 s cycle | Unstructured noise or a continuous recording of something else |

**Verdict: GENUINE OFF-AIR BAND AUDIO.** The WAV is a real, crowded 20 m FT8 band segment: many simultaneous
narrowband GFSK transmissions at different frequencies and levels, gated on the 15 s FT8 cycle, over a
wobbling receiver noise floor — consistent in every measurable respect with the kiwirecorder RSSI trace in
the log (blocks dipping to ≈ −102 dBm in the guard intervals, rising to ≈ −71 dBm mid-burst).
Nothing about it resembles a gen_ft8 product or any placeholder.

One measurement matters for §4: the burst grid's best-fit phase is at file offset **2.60 s**, and the
decoder-DT cluster implies **3.44 s** — not the 5.00 s implied by the log's banner timestamp (contrast at
5.00 s is −0.092, i.e. anti-aligned). **The banner `start_utc` precedes the first audio sample by ~1.6–2.4 s**
(kiwirecorder connect latency). Slot *attribution* is unaffected (slots are identified by window), but
absolute-time estimates from the banner carry ~±2 s uncertainty.

## 4. Independent re-decode (ft8_lib, UTC-slot-aligned)
Method: the new `lab/ft8_slot_decode.py` (see §5) — each UTC-aligned 15 s slot decoded exactly once with
`decode_ft8`. Two alignments were run: **primary** = the log's banner start (07:57:25Z; first boundary at
file 5.00 s), **sensitivity** = start +2.0 s (boundary at 3.00 s, per the §3 phase measurement).

Per-slot unique message counts:
| Slot (UTC) | Old stride method (union of its windows) | Slot-aligned, primary | Slot-aligned, sensitivity |
|---|---|---|---|
| 07:57:30 | 19 | 15 | 19 |
| 07:57:45 | 12 | 8 | 12 |
| 07:58:00 | 18 | 15 | 16 |
| 07:58:15 | 16 | 11 | 16 |
| 07:58:30 | 13 | 11 | 15 |
| 07:58:45 | **0 — never decoded** | 9 | 14 |
| **Total (slot, text)** | 78 implied, but merged to **58 texts** globally | **69** | **92** |

Findings:
- **All 58 of the log's unique texts are independently reproduced** by the sensitivity decode (58/58 overlap;
  0 log-only texts). Nothing in the headline claim was fabricated or mis-parsed.
- The headline **understates** the recording: the correctly aligned decode finds **92 distinct
  (slot, text) transmissions / 65 unique texts**, including **7 texts absent from the log's 58**:
  `C5R JH1FYC R-07`, `CQ F4NHL IN94`, `CQ IN3ADG JN56`, `IK1QLD PY7ZC RR73`, `MM7CEH F4FDR -03`,
  `OK2AB IU8RFW JN70`, `S55X EA4ITM IN80` — most from the **final slot (07:58:45), which the stride
  method never decoded at all** (its last window started at offset 74 s, putting that slot's signals
  at DT ≈ +4.4 s — outside decode_ft8's DT search range; see §6).
- The primary (banner-aligned) decode recovers 69 (slot, text) / 49 texts: with boundaries placed ~2 s
  late, signals start before each window and some lose their first ~1.6 s (incl. the leading Costas
  sync) — 14 of the log's texts drop out under this misalignment, which is exactly the failure mode
  the sensitivity alignment corrects. This is a *timestamp-accuracy* defect in the workflow, now
  documented in the workflow itself — not a data defect.
- Full per-message table (slot UTC, approx UTC = slot + DT, DT, frequency, text, in-58 flag):
  **`lab/audit/redecode_table.md`** (92 rows). Receiver for all rows: emeraldsdr (Carlow, Ireland),
  14074 kHz USB. Example rows: 07:57:30 slot — `CQ IW2NEF JN46` (291 Hz), `ZL1MED OZ4ACK JO65` (1006 Hz),
  `CQ P4/WE9V` (1066 Hz); 07:58:30 slot — `JA1LLG CT7BRV -15` (788 Hz), `CQ SP3DOF JO72` (1422 Hz).

## 5. Window-logic fix (what changed and why it is right)
Old logic (kiwisdr.yml heredoc, oracle_score.py): 15 s windows at a 2 s stride from an arbitrary file
start; dedup by message text across the whole recording. Defects, all now demonstrated on real data:
(i) each transmission decoded 2–3× (180 events for ≤92 transmissions); (ii) text-dedup collapses
*repeated transmissions in different slots* into one (e.g. `CQ IW2NEF JN46` was sent in ≥3 slots,
counted once); (iii) the final slot can fall entirely outside every window's decodable DT range and
vanish silently; (iv) no message can be attributed to its true UTC slot.

New logic — `lab/ft8_slot_decode.py`: given the recording start (ISO 8601 UTC), it computes
`offset_to_first_slot = (15 − (start_epoch mod 15)) mod 15`, decodes each UTC-aligned slot exactly once
(final partial slot zero-padded and marked PARTIAL), and dedups only identical (slot, text).
`kiwisdr.yml` now captures the attempt start into `REC_START_UTC` and calls this script instead of the
heredoc; `oracle_score.py` calls it with each recording's start resolved from `record_notes.txt`
(parallel-launch or sequential-fallback timestamp). Both changes are committed with this audit.

Deterministic test — `lab/test_ft8_slot_alignment.py` (log: `lab/results/ft8_slot_alignment_test.log`):
synthetic recording starting 7.30 s into a slot (offset must compute to 7.70 s); messages A/B/C placed
in three consecutive true slots, C deliberately spanning a naive window edge; one noise-only slot.
**RESULT: PASS** — A, B, C each recovered exactly once in their correct UTC slots (08:00:15 / :30 / :45),
noise slot empty; and the informational check confirms the naive slicing recovers C from *neither*
of the windows it straddles — the old logic provably loses exactly this case.

## 6. Parsing audit — could "58" be inflated by the counter?
Decoder behaviour, established from `ft8_lib/demo/decode_ft8.c` source *and* controlled runs
(stdout/stderr captured separately):
- Message lines are printed by `printf` to **stdout**, format `HHMMSS +SNR DT FREQ ~ TEXT`
  (for file input the time field is a literal `000000` placeholder — `tm_slot_start` is only set in live mode).
- **All** diagnostics go to **stderr** via `LOG()` → `fprintf(stderr, ...)`: `Sample rate …`,
  `Block size …`, a `#` progress line, `Max magnitude: …`, and finally
  `Decoded N messages, callsign hashtable size M`. In file mode, stdout carries *only* message lines:
  clean synthetic WAV → exactly 1 stdout line; noise-only WAV (RMS 800) → **empty stdout, `Decoded 0`**;
  busiest artifact slice → 18 stdout lines, `Decoded 18`.
- Within one run, `decode_ft8` dedups identical payloads itself (`Found a duplicate!` path), so its
  stderr count always equals its stdout message-line count (verified 1=1, 0=0, 18=18).
- Its DT search accepts only ≈ −1.6…+3.2 s offsets within the input file (empirical, from all runs
  above) — the mechanism behind both the stride method's design and its final-slot blindness (§4).
- One theoretical inflation path exists in the source: if message unpacking fails, the text becomes
  `Error [N] while unpacking!` and the line is still printed and counted. **It never fired here:**
  `grep -c "Error \["` on kiwisdr_ci.log = 0.

Old parser (quoted from the pre-fix heredoc in kiwisdr.yml; identical logic in oracle_score.py):
```python
m = re.search(r"Decoded (\d+) messages", p.stderr)
cnt = int(m.group(1)) if m else 0
...
lines = [ln for ln in p.stdout.splitlines() if "~" in ln]
msg = ln.split("~", 1)[1].strip()
if msg and msg not in unique: unique[msg] = ln
```
**Verdict: the count is trustworthy and could not have been inflated by diagnostics.** The event counter
reads the decoder's own CRC-gated count from stderr; the unique-text set is built only from stdout lines,
and stdout contains nothing but genuine message lines (FT8 message text cannot contain `~`, and no other
stdout output exists in file mode). Cross-checks all close: per-window counts in the log sum to exactly
180; every one of the 58 texts re-decodes independently from the raw audio (§4). If anything, 58 is
**conservative**: the true content is 65 unique texts / 92 transmissions, because the old windowing
missed a whole slot and merged cross-slot repeats.

## 7. Limitations of this audit
- Absolute UTC per message is ≈ slot + DT with ~±2 s uncertainty: the workflow's banner timestamp
  precedes first audio by ~1.6–2.4 s (§3), and decode_ft8's DT convention itself reads +1.36 s for a
  gen_ft8 file placed exactly at a slot start. Slot attribution (the scientifically important part) is exact.
- decode_ft8's "SNR" column is `score × 0.5` (source, decode_ft8.c) — a heuristic, not a calibrated
  2500 Hz SNR; this audit makes no use of it.
- Two decoded texts contain `<...>` (hashed callsigns that a single 90 s session cannot resolve);
  they are genuine CRC-valid decodes but their sender callsigns are unknown.
- No external corroboration (e.g. PSK Reporter / WSPRnet lookup of the same callsigns in the same
  minutes) was performed; the internal evidence (artifact hash chain, spectral structure, RSSI trace,
  CRC-checked independent re-decode) is self-contained and mutually consistent.
- This audits ONE 90 s recording from ONE receiver on ONE frequency. It establishes that the pipeline
  genuinely receives and decodes real off-air FT8 — nothing more (no transmission, no two-way contact,
  no claim about any other band, time, or receiver).

## 8. Bottom line
- Artifact integrity: **verified** (hash matches GitHub's digest; committed log ≡ artifact log).
- WAV authenticity: **genuine off-air** 20 m FT8 band audio (14+ simultaneous signals, real noise/AGC behaviour).
- The 58 messages: **all real, all reproduced independently** — and conservative; the recording actually
  contains **92 decodable transmissions (65 unique texts)** under correct slot alignment.
- Method flaws found (stride slicing, text-dedup, banner-timestamp latency) are **fixed and regression-tested**
  in `lab/ft8_slot_decode.py` + `lab/test_ft8_slot_alignment.py`, wired into kiwisdr.yml and oracle_score.py.
