# Nature-Mirror Mesh — Phase 2 Lab Results ($0 cloud path)
**Date:** 2026-10-20 · **Machine:** same sandbox VM (no radio hardware; **no radio transmission was made or claimed**) · Budget: $0 — free/open-source only

## Task 1 — FT8 decode from source (ft8_lib): ✅ PASS
- Cloned `https://github.com/kgoba/ft8_lib` → `lab/ft8_lib`; built with its Makefile (`make`, gcc `-O3`, `-lm`): `libft8.a`, `gen_ft8`, `decode_ft8`, `test_ft8` all built cleanly.
- `gen_ft8 "CQ NMM PK"` → 15 s, 12 kHz WAV. `gen_ft8` has **no noise option**, so calibrated Gaussian noise was added with numpy (seed 42, RMS-calibrated, full-band RMS SNR).
- `decode_ft8` output contained the exact sent text at **every** level — evidence in `lab/results/ft8_lib_test.log`:
  - clean: `000000 +16.5 +1.36 1000 ~  CQ NMM PK` ("Decoded 1 messages")
  - SNR −5 dB: decoded `CQ NMM PK` · SNR −10 dB: decoded `CQ NMM PK` · SNR −15 dB: decoded `CQ NMM PK` · SNR −20 dB: decoded `CQ NMM PK`
- This closes the phase-1 gap: **FT8 decode is now verified**, from source, at weak-signal levels. (Full-band RMS SNR is a harsher measure than the usual 2500 Hz reference-bandwidth SNR.)

## Task 2 — Three-node LXMF mesh with transport forwarding: ✅ PASS
- Script: `lab/lxmf_mesh3_test.py`. Topology: sender **S** → transport node **T** (`enable_transport = True`, TCP servers on 127.0.0.1:51721 + :51722) → receiver **C**. **S and C share no interface** — each has exactly one TCP client interface, both pointing at T; the only possible path is S → T → C (stated in the script header).
- Evidence (canonical log `lab/results/lxmf_mesh3_final.log`, copied to `lab/results/lxmf_mesh3_test.log`; script exit code 0; run completed in ~20 s; token file on disk matches):
  - `[S] path to C found: hops_to(C)=2` — two hops proves the routed path via T.
  - `[T] learned path to C: hops_to(C)=1` and `[T] relay job done (C received the message); T forwarded traffic between S and C`.
  - `[C] DECRYPTED MESSAGE RECEIVED: NMM-MESH3-20261020-073213` — sent token == received token, exact match.
  - `[S] delivery confirmed by router state=DELIVERED (end-to-end, via T)`.
- **Flakiness found and fixed (honest record):** the first runs were intermittent — 2 FAIL runs (`[S] TIMEOUT: no path to C`, tokens …071913 / …072917) interleaved with PASS runs. Root cause: the sender re-issued `request_path()` every 0.5 s, which interferes with Reticulum's path-request handling, and the nodes had short head-starts. Fix: re-request at most every 5 s + longer startup head-starts (T 5 s, C 8 s). After the fix, the foreground verification run passed cleanly in ~20 s.
- Meaning: multi-hop, transport-relayed, end-to-end encrypted LXMF delivery works — the mesh property the multi-mirror backend needs (a gateway/relay node can carry traffic between clusters it alone connects).

## Task 3 — KiwiSDR $0 real-signal reception: ❌ FAIL (sandbox network policy — documented, not faked)
- Tooling: real kiwiclient cloned from `github.com/jks-prv/kiwiclient` → `lab/kiwiclient_repo` (PyPI's `kiwiclient 1.0.11` is an unrelated package). `pypng` + `websocket-client` installed.
- Receivers: the kiwisdr.com/public list is behind an interactive click-gate and rx.linkfanel.net timed out via the proxy; candidate hosts came from kiwisdr.com's own info page. HTTP `/status` checks **succeeded** for four live receivers on other continents: emeraldsdr (Carlow, **Ireland**), DX Central (Louisiana, **USA**), VK4KY (Queensland, **Australia**), London (Ontario, **Canada**). Chosen: Ireland, 14074.0 kHz USB (20 m FT8), 200–3200 Hz, 120 s + a 45 s diagnostic retry.
- **Blocker (exact):** the KiwiSDR audio stream is a raw-TCP websocket; this sandbox denies direct TCP — only proxy-mediated HTTP(S) works. kiwirecorder looped: `Failed to connect, sleeping and reconnecting error='Wrong status line format: 'muse: Other TCP connections is turned off for this assistant. To allow it, ask the user to open Muse settings -> Permissions -> Direct network protocols and switch other_tcp from Deny to Ask.\r\n''`, then `[Errno 32] Broken pipe`. **0 bytes recorded; no off-air decode is claimed.** Full record: `lab/results/kiwisdr_test.log`.
- Unblock path: permit direct TCP for the assistant, or run kiwirecorder on Colab / any normal machine and feed the WAV to `lab/ft8_lib/decode_ft8` (decoder already proven in Task 1).

## Task 4 — Free-cloud packaging: ✅ DONE
- `.github/workflows/lab.yml` (YAML-validated): on `workflow_dispatch` + push to main — ubuntu-latest, Python 3.12, `pip install rns lxmf`, runs `lab/lxmf_two_node_test.py` (4 min step timeout), then clones + builds ft8_lib in CI and runs the encode → noise (−10/−15 dB) → decode round-trip with an assert on the decoded text. Free on GitHub's runners for public repos.
- `colab/Nature_Mirror_Mesh_Colab.ipynb` (nbformat 4, validated: JSON parses, all 5 code cells compile): markdown + code cells that on free Colab (1) build ft8_lib and run the FT8 round-trip, (2) `pip install rns lxmf`, (3) run a self-contained two-node LXMF test inline (the embedded script, `colab/colab_lxmf_test.py`, was **run locally here first and PASSED**: token `NMM-COLAB-20261020-072753`, RESULT: PASS), (4) honesty notes. A markdown cell documents the `apt-get install wsjtx` alternative.
- README.md gained a "Phase 2 ($0 cloud path)" section linking the workflow, the notebook, and these results.

## Phase-2 honest summary
- ✅ FT8 decode verified from source, down to −20 dB full-band RMS SNR (was NOT verified in phase 1).
- ✅ Three-node mesh with a real transport relay (S → T → C) verified, with hop-count proof.
- ❌ Real off-air KiwiSDR reception blocked by sandbox direct-TCP policy — exact error recorded; everything except the raw socket is ready.
- ✅ $0 execution paths packaged for GitHub Actions and Google Colab.
