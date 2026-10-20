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
