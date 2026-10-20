# FINAL CONFIDENCE REPORT — Nature-Mirror Mesh, digital-lab phase

**Date (UTC):** 2026-10-20
**Phase closed:** the digital lab. Everything below was produced with
simulated channels, recorded real-world audio, or free cloud runners.
**$0 was spent, and zero RF was emitted — stated once, plainly: every
"transmission" in this project so far is either a simulation, a
recording of other stations' real signals, or a log on a free CI
runner. No radio has ever transmitted for this project.**

Grading style follows `EVIDENCE_REVIEW.md` (Scientific Agent Skills —
scientific-critical-thinking workflow): certainty is per claim, scoped
exactly as worded, with the reason in one line and the falsifier /
remaining gap named.

---

## 1. The complete proof ladder

| # | Rung | Result | Evidence |
|---|---|---|---|
| 1 | Research & invention: Nature-Mirror Mesh concept (DTN chat over ionosphere / meteor / Moon mirrors, Reticulum+LXMF glue, propagation oracle) | Design + 33-source scientific packet | `~/workspace/research_notes/physics-invention-offline-chat.md`, `~/workspace/research_notes/offline-chat-scientific-packet.md` |
| 2 | LXMF encrypted delivery, 2 nodes (local ×2 + GitHub CI) | **PASS** — tokens exact-match after decryption; sender DELIVERED; CI run 39388808248 | `lab/results/RESULTS.md`, `lab/results/lxmf_test.log`, `lab/results/ci_run_39388808248.log` |
| 3 | Mesh3 (S→T→C, TCP) repetition | **10/10 PASS local** (260.9 s) + **10/10 PASS in CI** (run 39401755454), against the pre-registered ≥80% remedy criterion | `lab/results/MESH3_REPETITION.md`, `lab/results/mesh3_repeat_local.log` |
| 4 | FT8 synthetic codec (ft8_lib, built from source) | Encode→decode exact at clean, −5, −10, −15, **−20 dB** full-band RMS SNR locally; −10/−15 dB reproduced in CI | `lab/results/ft8_lib_test.log`, CI log above |
| 5 | **Off-air reception** (KiwiSDR, emeraldsdr Carlow IE, 14074 kHz, 90.3 s WAV) | Real FT8 decoded from live band audio; audit: **92 transmissions / 65 unique texts** (all 58 originally logged texts reproduced); **PSK Reporter corroboration** — independent receivers spotted the same senders at frequencies matching our decodes to **≤1 Hz** | `lab/results/kiwisdr_test.log`, `lab/results/AUDIT_kiwisdr.md`, `lab/audit/` |
| 6 | Propagation oracle, run #1 | Ireland: **WRONG** (predicted 20 m better, 0.938 vs 0.910; measured 20 m = 74, 40 m = 78 unique). Australia: **INDETERMINATE** (receiver timed out twice, 0 bytes). Recorded as-is; design fix (4 sites, slot-aligned counting, commit-back retry) built for run #2 | `lab/results/ORACLE_RUN1_POSTMORTEM.md`, `lab/results/oracle_prediction.json` |
| 7 | TX chain (content crosses simulated HF as FT8 beacon) | **PASS** — token `NMM-TX-ZD9ULBSE7SIT` recovered exactly at −5, −10 (pre-stated criterion), −15 dB, and −10 dB +30 Hz offset; 30 s airtime. Honest scope: LXMF *content* crossed as beacon; the 142 B packet bytes did not fit FT8 | `lab/results/TX_CHAIN_TEST.md`, `lab/results/tx_chain_test.log` (run-1 failure preserved: `TX_CHAIN_TEST_run1_failed_mapping.md`) |
| 8 | **DIGITAL LAB 1** — full LXMF packet over ONE simulated Watterson hop (invented 16-FSK + Reed-Solomon modem, `lab/nmm_modem.py`) | **PASS** — full packed packet (147 B) byte-exact **9/10 at −10 dB** (pre-registered ≥8/10); sweep PASS at 0/−5/−10 dB, FAIL at −15 dB; +40 Hz offset bonus YES; 29.5 s airtime/packet, 4.99 B/s effective | `lab/results/MODEM_PACKET_TEST.md`, `lab/results/modem_packet_test.log` (attempt 1 preserved alongside) |
| 9 | **DIGITAL LAB 2** — two-hop mesh, every link the modem (custom RNS interface, `lab/modem_interface.py`, frame_repeats=3) | **PASS** — token `NMM-MODEMMESH-ARGV8PP598JR`, LXMF hash match at C, S hops_to(C)=2, T hops_to(C)=1, delivery_attempts=1; total simulated airtime 2,800.7 s, sender-phase wall 26 s, max RNS packet 244 B (frame capacity 4096 B) | `lab/results/MODEM_MESH_TEST.md`, `lab/results/modem_mesh_test.log` (failed attempt 1 preserved) |
| 10 | **DIGITAL LAB 3** — long messages over the Lab-2 mesh | **PASS** — 500 B (packed 623 B) and 1500 B (packed 1,623 B) content delivered S→T→C with content SHA-256 + LXMF hash validated at C, **attempt 1 each**; airtime 3,142.6 s / 4,463.5 s; wall 31.4 s / 31.0 s (sender phase). Required finding+fixing a real RNS/interface race — see §3 | `lab/results/LONGMSG_TEST.md`, `lab/results/longmsg_mesh_test.log`, `lab/longmsg_mesh_test.py` |

## 2. Updated claim table

| Claim | Certainty now | One-line reason | What remains unproven |
|---|---|---|---|
| LXMF encrypted delivery works end-to-end between independent nodes | **High** | Exact-token matches + DELIVERED state across ≥4 runs in 3 environments (local, Colab-style, GitHub CI) | Nothing for the scoped claim (loopback links) |
| 3-node routed mesh (S→T→C) forwards correctly | **High** (was Low in EVIDENCE_REVIEW) | The review's own remedy executed: 10/10 local + 10/10 CI post-fix, zero recurrence of the path-discovery failure | Radio-link version is covered separately by Labs 2–3, not by this claim |
| ft8_lib decodes synthetic FT8 to −20 dB (local) | **Moderate** | Exact decodes logged; CI agrees at −10/−15; single message/seed per level, Gaussian noise only | A seed × message × SNR failure-threshold sweep |
| The off-air WAV is genuine live 20 m audio (Carlow, IE, ≈07:57 UTC) | **Moderate** | Forensics (14 simultaneous tone tracks, 82× noise-floor variation, 15 s gating contrast +0.611) + PSK Reporter matches ≤1 Hz; receiver identity rests on the workflow's own connection record | A second simultaneous receiver cross-match |
| 65 unique texts / 92 transmissions were really on air in that window | **Moderate** | Independent slot-aligned re-decode reproduced all 58 original texts + 7 more; LDPC+CRC-gated; exact count is alignment-sensitive (truth ≥58, most likely 65); absolute time ±2 s | A WSJT-X cross-decode of the preserved WAV |
| PyFT8 decode | **Not verified** (High certainty in the negative record) | Documented upstream defects + environment limits; never succeeded anywhere in this project | Superseded — ft8_lib is the project's FT8 codec; PyFT8 is not on the path |
| A full LXMF packet crosses one simulated HF hop at −10 dB | **Moderate** | 9/10 byte-exact against a pre-registered ≥8/10, fresh packet+seed per trial, one preserved imperfect attempt | Real-channel (recorded-noise/fading diversity) replication; larger n |
| A 2-hop all-modem mesh delivers LXMF end-to-end | **Moderate** | One full PASS after one preserved FAIL (fixed by frame_repeats=3); same machinery then carried Labs 3's sizes on attempt 1 | Repetition count (n>1 per configuration) |
| Long messages (500 B, 1500 B content) cross the 2-hop modem mesh | **Moderate** | Both PASS on attempt 1 post-fix with hash+content validation; the pre-fix failure mode was found, root-caused with stack traces, and fixed at the interface | Sizes >1500 B untested (envelope is "at least 1500 B", not "at most") |
| The propagation oracle picks the better band | **Unproven** | Run #1: 1 WRONG + 1 INDETERMINATE of 2 sites — the protocol falsified the heuristic, as designed | Oracle run #2 (4 sites, fixed workflow) and a run series; heuristic v1 is a placeholder, not an ITU-R P.533 model |
| Real RF **transmission** of NMM traffic | **Unproven** | Nothing has ever been transmitted; all TX evidence is simulated channels | Licensed hardware + licensed operator; note amateur bands prohibit encryption, so encrypted chat belongs on licence-free links (e.g. LoRa) or non-amateur allocations |
| Meshtastic / LoRa physical mesh | **Unproven** | No hardware exists in this project; library present, MQTT path has no client in the installed version | Hardware in hand |

## 3. The Lab-3 finding (why it matters beyond this lab)

Three consecutive 500 B attempts scored FAIL while the sender reported
DELIVERED and no error existed anywhere. Instrumented runs proved the
LXMF delivery callback fired with `resource.status = 3 (TRANSFERRING)`
instead of 6 (COMPLETE): RNS's `Resource.assemble()` sets COMPLETE and
sends the proof, and only then calls the app callback — but
`Resource.receive_part()` resets the status to TRANSFERRING on every
part packet it is handed, and this lab's interface (frame_repeats=3 ×
two hops) kept injecting duplicate part copies during that window.
**Fix:** interface-level duplicate suppression in
`lab/modem_interface.py` (each distinct payload injected at most once
per 300 s; later copies counted `rx_dup`). Verified by instrumentation
(status=6, validated delivery) and by the official run; the fix also
cut 500 B airtime from 7,564.9 s to 3,142.6 s. Full record:
`lab/results/LONGMSG_TEST.md`. **App-phase rule carried forward: any
interface that can deliver duplicates must dedup below RNS, or large
messages can vanish silently while every layer reports success.**

## 4. Numbers summary (from the logs)

| Quantity | Value | Source |
|---|---|---|
| Lab 1 airtime per full packet (147 B) | 29.5 s | MODEM_PACKET_TEST.md |
| Lab 2 total simulated airtime (short message, 2 hops) | 2,800.7 s (wall 26 s) | MODEM_MESH_TEST.md |
| Lab 3 airtime — 500 B content, 2 hops | 3,142.6 s ≈ 52 min (wall 31.4 s) | LONGMSG_TEST.md |
| Lab 3 airtime — 1500 B content, 2 hops | 4,463.5 s ≈ 74 min (wall 31.0 s) | LONGMSG_TEST.md |
| TX-chain beacon airtime (token as 2 FT8 slots) | 30 s per message | TX_CHAIN_TEST.md |
| Mesh3 repetition wall time (10 runs, local) | 260.9 s total | MESH3_REPETITION.md |
| Money spent, whole project | **$0** | — |
| RF emitted, whole project | **None** | — |

Simulated airtime is what the frames would occupy on a real ~40 bit/s
HF link; wall clock is CPU time on free machines and is far shorter.
Latency on real HF would be dominated by airtime + propagation
conditions, not by computation.

## 5. Readiness statement — what the app phase may now assume

Per the project rule (*app only after everything is ready*), the
digital lab is now **complete**: every layer the app will stand on has
been executed and measured, and the known failure modes are documented
with fixes. Precisely:

**Ready (proven, measured):**
- Protocol stack: Reticulum + LXMF, encrypted, store-and-forward,
  transport-forwarded over 2 hops — over TCP (High) and over the
  simulated-radio modem interface (Moderate, Labs 2–3).
- Message envelope: content up to **at least 1500 B per message**
  delivered over 2 simulated HF hops at −10 dB/hop. Design centre:
  ≤500 B for routine traffic (≈52 min worst measured 2-hop airtime at
  −10 dB); 1500 B is the proven ceiling, not the norm.
- Physical-layer settings: `frame_repeats = 3` **and** interface
  duplicate suppression ON (both are load-bearing — Lab 2 attempt 1
  and Lab 3's debugging record show what happens without each).
- Tiny-payload fast path: FT8 beacon slots carry short content in
  30 s when the modem path is overkill (TX-chain PASS).
- Receive path from the real world: off-air FT8 reception + decode is
  proven against live band audio (KiwiSDR), corroborated independently.

**App v1 should therefore contain:** text chat on LXMF identities;
store-and-forward UX with honest delivery states (queued → sent →
proof-received; no real-time promises); the modem interface with
repeats=3 + dedup; message-size guidance in the UI (≈500 B soft
target, 1500 B hard-proven max); the FT8 beacon mode for short
messages; the propagation oracle shown as a *hint* labelled heuristic
v1 (accuracy unproven — run #2 pending); a KiwiSDR listen-only mode.

**Not ready, and the app must not claim otherwise:** real RF
transmission (needs licensed hardware/operator — the next phase is
physical, not digital); oracle accuracy (needs the run series);
PyFT8 (dropped; ft8_lib is the codec); Meshtastic hardware mesh
(untested, no devices). The Earth-Chord neutrino idea remains a
labelled hypothesis in the concept paper, not a feature.

**Digital-lab phase: CLOSED. The next phase is the app — on the user's
word, per the standing rule.**
