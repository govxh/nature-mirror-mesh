# Nature-Mirror Mesh — Lab Results
**Date:** 2026-10-20 · **Machine:** sandbox VM (no radio hardware — software tests only; **no radio transmission of any kind was made or claimed**)

## Environment notes (verified during this session)
- Python 3.12.3 venv at `lab/venv`.
- pip installs needed the sandbox CA fix: `SSL_CERT_FILE=/tmp/combined-ca.pem` (combined bundle) — worked.
- **This sandbox blocks ALL UDP sends** (`Errno 1 / Operation not permitted`), even UDP to 127.0.0.1 from a plain Python socket. TCP loopback works fine. The LXMF test was therefore switched from a UDP interface pair to TCP interfaces (documented in the test source).

## Installed (pip, into lab/venv)
| Package | Version | Import verified |
|---|---|---|
| rns (Reticulum) | **1.5.7** | ✅ `RNS.__version__ == 1.5.7` |
| lxmf | **1.2.1** | ✅ |
| meshtastic | **2.7.11** | ✅ (library only — see below) |
| pyft8 (PyFT8) | **4.0.3** | ⚠️ partial — see FT8 section |
| numpy / scipy | latest | ✅ (PyFT8 deps) |

## Test 1 — LXMF two-node end-to-end encrypted delivery: ✅ PASS
- Script: `lab/lxmf_two_node_test.py` (two separate OS processes, two separate Reticulum config dirs; Node A = `TCPServerInterface` on 127.0.0.1:51711, Node B = `TCPClientInterface`; local link only).
- Flow: A registered an LXMF delivery identity and announced → B requested path, recalled A's identity → B sent an LXMF message with a unique runtime token → A's delivery callback printed the **decrypted** content → orchestrator compared strings and exited 0.
- **Run 1 token:** `NMM-TEST-20261020-065214` — sent == received ✅
- **Run 2 token (saved log, `lab/results/lxmf_test.log`):** `NMM-TEST-20261020-065226` — sent == received ✅, sender router state reached `DELIVERED`, `SCRIPT_EXIT=0`.
- First attempt with a UDP interface pair FAILED in this sandbox (UDP EPERM, above) — that failure and its log are part of the record; the fix was TCP, which is also one of the link options the project brief allowed.
- Meaning: the Nature-Mirror Mesh **"glue" layer (Reticulum + LXMF store-and-forward encrypted messaging) works end-to-end today**, over a local link standing in for a future radio link (LoRa/RNode, packet radio, HF) — Reticulum treats all of those as interchangeable interfaces.

## Test 2 — Meshtastic: ⚠️ library only
- `meshtastic` Python package **2.7.11** installed and imports fine; the CLI entry points (`meshtastic`, `mesh-tunnel`, `mesh-analysis`) are present in the venv.
- **`meshtasticd` binary: NOT available** (not in pip, not on PATH). The Python library alone can only talk to a physical Meshtastic radio (USB/BLE/Wi-Fi) or to a running `meshtasticd`.
- One-line verdict: **hardware or meshtasticd is required — no software/simulated radio path exists in this VM.**

## Test 3 — FT8 weak-signal path: ⚠️ PARTIAL / NOT VERIFIED
- `apt-cache policy wsjtx` returned no candidate in this sandbox's apt sources (WSJT-X not installable here without adding sources; its GUI/audio stack is a poor fit for this VM anyway).
- PyPI route: **PyFT8 4.0.3**. Full `pip install pyft8` FAILS here because its `pyaudio` dependency needs PortAudio system libraries to build. Workaround used: `pip install --no-deps pyft8` + `numpy` + `scipy`, plus a `sys.modules` stub for `pyaudio` in the test script.
- PyFT8 ships **no sample WAV file**, and its `Receiver` class is bound to a live audio input device, so a file-based decode could not be run as designed.
- Attempted instead (`lab/ft8_codec_test.py`): symbol-level codec round trip — encode `CQ NMM1 AA00` → 79 FT8 symbols (encode side works), feed soft symbol probabilities into the library's LDPC decoder / raw-91 decoder → **both returned `None` (decode did not verify)**. Two upstream quirks were found and patched around in the test: `transmitter.pack_message` calls a non-existent `add_call_hashes()` (only `receiver.add_call_hash` exists), and `receiver.py` hard-imports `pyaudio` at module top.
- Verdict: **FT8 encode path demonstrated; decode NOT verified in this VM.** Shortest path to a verified decode: run WSJT-X (which ships sample FT8 WAVs) or PyFT8 on a machine with PortAudio + an audio device, or feed PyFT8 a real off-air recording via a file-capable fork.

## GitHub
- `gh auth status` on this VM: **"You are not logged into any GitHub hosts."** Per project rules no login was attempted and no credentials were used.
- Status: **ready to push, gh not authenticated on VM** — the folder is a git repository with everything committed locally; one `gh auth login` + `gh repo create nature-mirror-mesh --public --source=. --push` (run where the account is authenticated) publishes it.

## Honest summary
- ✅ Proven today: Reticulum/LXMF encrypted, store-and-forward chat transport between two independent nodes over a local link (the protocol layer Nature-Mirror Mesh is built on).
- ⚠️ Not proven here (needs hardware or a non-sandbox machine): Meshtastic radio link, FT8 audio decode, and any actual over-the-air mirror (ionosphere / meteor / Moon).
- ❌ Nothing in this lab transmitted any radio signal.

---

# CI verification — GitHub Actions (added 2026-10-20, evidence-preservation pass)
The Phase-1/2 lab proofs were re-run independently on GitHub's free runners. This section records the successful run exactly as logged; nothing below is paraphrased where quotation is used.

- **Workflow:** "Nature-Mirror Mesh Lab ($0 CI)" — `.github/workflows/lab.yml`
- **Run:** #4, ID **39388808248** — https://github.com/govxh/nature-mirror-mesh/actions/runs/39388808248
- **Commit:** `7e7a24f` (branch `main`, triggered via push) · started Oct 20, 2026, 12:47 PM GMT+5 · total 33s · job `lab` **SUCCESS** in 30s
- **Runner environment:** ubuntu-latest, Python 3.12.15 · install step verbatim: `pip install rns lxmf numpy` → `Successfully installed cffi-2.1.1 cryptography-50.0.2 lxmf-1.2.1 numpy-2.5.4 pycparser-3.11 pyserial-3.5 rns-1.5.7`
- **Run history note:** run #1 (commit `63b3841`) FAILED at the FT8 step with `ModuleNotFoundError: No module named 'numpy'`; the one-line fix (add `numpy` to the install step) made runs #2, #3 and #4 succeed. Full verbatim step logs of run #4: `lab/results/ci_run_39388808248.log`.

## CI Check 1 — LXMF two-node encrypted delivery: ✅ PASS
- Commands (as run by the workflow): `cd lab` → `python lxmf_two_node_test.py`
- Verbatim key output:
  - `Token: NMM-TEST-20261020-074713`
  - `[A] DECRYPTED MESSAGE RECEIVED: NMM-TEST-20261020-074713`
  - `[B] delivery confirmed by router state=DELIVERED`
  - `RESULT: PASS — LXMF end-to-end encrypted delivery verified over local TCP link`
- Sent token == received token, exact match, on a machine independent of the dev sandbox.

## CI Check 2 — ft8_lib encode → noise → decode (SYNTHETIC audio): ✅ PASS
- Commands: `cd lab/ft8_lib` → `./gen_ft8 "CQ NMM PK" /tmp/ft8_clean.wav 1000` → Python heredoc adds RMS-calibrated Gaussian noise (numpy, seed 42) at SNR **−10 dB** and **−15 dB**, writes WAVs, runs `./decode_ft8` on each and asserts the text.
- Verbatim decoder output:
  - Encoder: `Packed data: 2c 91 43 6f e5 4a 9f 8a 20 00`
  - At **−10 dB**: `000000 +15.5 +1.36 1000 ~  CQ NMM PK`
  - At **−15 dB**: `000000 +12.5 +1.36 1000 ~  CQ NMM PK`
  - Final line: `FT8 ROUND-TRIP: PASS`
  - (The +15.5/+12.5 figures are the decoder's own reported dB values, not the input SNR.)

## What these CI results do and do NOT establish — read carefully
- ✅ **Established:** the Reticulum/LXMF encrypted-delivery proof and the **ft8_lib** (kgoba/ft8_lib, C library) decode of a **synthetically generated** FT8 WAV with software-added noise are reproducible on a clean third-party machine (GitHub runner), not just in the dev sandbox.
- ⚠️ **PyFT8 decode remains NOT VERIFIED.** Phase-1 Test 3 above stands unchanged: PyFT8 4.0.3's decode never verified. The CI success belongs to a *different library* (ft8_lib) and must not be cited as a PyFT8 result.
- ❌ **Real off-air reception is NOT established by this run.** The CI audio was generated by `gen_ft8` itself — no radio receiver, antenna, or live signal was involved, and **no radio transmission occurred** (CI is receive/decode-only software work; the sandbox lab likewise transmitted nothing).
- **Limitations:** single test message (`CQ NMM PK`); SNR is full-band RMS as computed by the generator script, not a calibrated RF measurement; the LXMF link is localhost TCP standing in for a radio link, not a radio link. Off-air proof requires decoding a genuine received signal — the pending experiment for that is the KiwiSDR reception workflow (`.github/workflows/kiwisdr.yml`), which records a public receiver's live audio on a GitHub runner and decodes it with this same ft8_lib.
