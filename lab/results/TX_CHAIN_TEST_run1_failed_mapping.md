# Transmission-Chain Test (Experiment A) — Results

Date (UTC): 2026-10-20 09:38

## Design
Real LXMF message (sender node B -> receiver node A's real delivery destination, built from A's published public key) whose content is a unique token. The token crosses a simulated HF channel as a 2-slot FT8 beacon; node A validates and registers delivery of the recovered content at its radio-delivery point. The two node processes have NO network interface between them, so the audio chain is the only path the content can take.

- Ground-truth content: `NMM-TX-W6MZJNV7ZBSD`
- LXMF message_id: `cd8fef83b1235a7b193e9ff4c6d795d9a96952bf91108498214c5e472ef5f1b6`
- Packed LXMF size: 142 bytes (a full LXMF packet does NOT fit FT8 slots; the content crosses as a token beacon — see test header).
- Beacon messages: `CQ W6MZJN BP01` / `W6MZJN V7ZBSD BP02`

## Beacon mapping
Content = `NMM-TX-` + CHUNK1 + CHUNK2. Each chunk is 6 chars shaped as a standard FT8 callsign with exactly one digit at position 2 ([A-Z][0-9][A-Z]4) — the only callsign shape verified to round-trip through ft8_lib (free text does NOT round-trip in this build: the encoder packs it but decode_ft8 prints `<...>`). Slot 1 = `CQ CHUNK1 GRID`, slot 2 = `CHUNK1 CHUNK2 GRID`; GRID = 2 checksum letters (over the 12 payload chars, s = sum((i+1)*ord) mod 324, base-18 letters A-R) + sequence `01`/`02`. A recovery is accepted only if both slots decode, chunk1 agrees, and the checksum recomputes.

## Channel model (numpy, seeded per condition)
Watterson-style two-path fading: delays 0.5 ms / 2.0 ms, mean powers 0.6 / 0.4, per-path Rayleigh envelope with Gaussian Doppler spectrum sigma = 0.7 Hz; AWGN added to reach the target full-band RMS SNR (RMS measured on the faded signal over the full 12 kHz band — same SNR definition as this project's earlier ft8_lib tests). One run adds a +30 Hz frequency offset (FFT-Hilbert shift) before fading.

## Per-condition results

| Condition | Target SNR (full-band RMS) | Freq offset | Decoded texts | Recovered | Verdict |
|---|---|---|---|---|---|
| snr-05 | -5 dB | +0 Hz | CQ <...> BP01<br><...> <...> BP02 | `None` | FAIL |
| snr-10 | -10 dB | +0 Hz | CQ <...> BP01<br><...> <...> BP02 | `None` | FAIL |
| snr-15 | -15 dB | +0 Hz | CQ <...> BP01<br><...> <...> BP02 | `None` | FAIL |
| snr-10-off30 | -10 dB | +30 Hz | CQ <...> BP01<br><...> <...> BP02 | `None` | FAIL |

Slots per transmission: 2 (15 s each) = 30 s simulated airtime per condition; 4 conditions exercised = 120 s total simulated airtime.

Node A delivery of the -10 dB recovery: NOT completed / mismatch

## Verdict

**FAIL** — pre-stated criterion: exact token recovery at -10 dB (no offset) plus A's validated delivery matching ground truth.

## Honest scope
Baseband audio + a simulated channel model; **no RF was emitted** and nothing was transmitted over the air. No LXMF packet bytes crossed the channel — the message CONTENT crossed as an FT8 beacon, per the design above. The final physical step is feeding this same WAV to any SSB transmitter and receiving it on a real receiver — the receive half of that step was already proven with real off-air KiwiSDR audio in this project; the transmit half remains unproven and requires licensed hardware.
