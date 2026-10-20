# Full LXMF Packet over nmm_modem — Results (DIGITAL LAB 1)

Date (UTC): 2026-10-20 09:55

## Question
tx_chain_test.py proved a token *beacon* can cross a simulated Watterson HF channel, but the real packed LXMF packet never crossed it (FT8 cannot carry arbitrary packet bytes). This test runs the invented alternative — lab/nmm_modem.py — and asks whether the FULL packed packet crosses, byte-exact.

## Pre-registered criterion
>= 8/10 byte-exact recoveries at -10 dB, fresh LXMF packet and fresh channel seed per trial. Stated in the test header before any run.

## Modem (nmm_modem.py)
16-FSK (525-2025 Hz, 100 Hz spacing), 40 ms symbols (100 bps raw), non-coherent detection on the symbol-aligned STFT frame; preamble + sync acquisition over a +/-50 Hz offset grid; 5x-repeated length header; plain block = length + payload + CRC-32; Reed-Solomon (K=100, NSYM=72, 2t+e<=72 with margin-based erasure decoding, threshold 1.6) with column interleaving across chunks.

- Sweep packet: token `NMM-MODEM-3UN4D5FJCU6N`, packed 147 bytes, SHA-256 `ea5251bcb908e4a77a792d5abf28aa5790d6ee1fb00b766f04948172756e1e61`
- LXMF message hash: `1775a570deaac6e6b3fb2ba59322bd05a690d6a5b0bfd1ee4f23af09de6169b9`
- Airtime per packet: 29.5 s; effective throughput 4.99 payload bytes/s (store-and-forward tolerates this; HF messaging is not a streaming medium)

## Channel
tx_chain_test.apply_channel, unchanged: two paths (0.5 ms / 2.0 ms, powers 0.6 / 0.4), Rayleigh envelopes, Gaussian Doppler sigma = 0.7 Hz, AWGN to the target full-band RMS SNR.

## SNR sweep (one run per level, same packet)

| SNR (full-band RMS) | Byte-exact | LXMF-valid |
|---|---|---|
| +0 dB | YES | YES |
| -5 dB | YES | YES |
| -10 dB | YES | YES |
| -15 dB | NO | NO |

Bonus run: +40 Hz frequency offset at -10 dB — byte-exact: YES (not gated).

## Reliability @ -10 dB (fresh packet + seed per trial)

| Trial | Token | Packed bytes | Byte-exact | LXMF-valid |
|---|---|---|---|---|
| 1 | `NMM-MODEM-EP1F9O7NJDCK` | 147 | YES | YES |
| 2 | `NMM-MODEM-HR30RN2FUNFD` | 147 | YES | YES |
| 3 | `NMM-MODEM-6N3N3UKTIFCX` | 147 | YES | YES |
| 4 | `NMM-MODEM-GMFZMA9Z86ZI` | 147 | YES | YES |
| 5 | `NMM-MODEM-KZZNLS4W3032` | 147 | NO | NO |
| 6 | `NMM-MODEM-PNBB7ME89JWL` | 147 | YES | YES |
| 7 | `NMM-MODEM-DHL375KSAXRQ` | 147 | YES | YES |
| 8 | `NMM-MODEM-228OY4VO2FR4` | 147 | YES | YES |
| 9 | `NMM-MODEM-5HFY9YYBO2IA` | 147 | YES | YES |
| 10 | `NMM-MODEM-1T55YC0VD7S0` | 147 | YES | YES |

Byte-exact: **9/10**; LXMF-validated: **9/10**.

## Verdict

**PASS** — pre-registered criterion >= 8/10 byte-exact at -10 dB: met (9/10).

## Attempt history
Attempt 1 (preserved as modem_packet_test_attempt1.log / MODEM_PACKET_TEST_attempt1.md) already met the byte-level criterion (10/10 at -10 dB), but its LXMF column read NO throughout: the validator compared unpack_from_bytes' bytes content against a str token (a test-harness type bug, not a data failure — the unpacked content and LXMF message hash in fact match). Attempt 1's bonus offset run also failed at the receiver's sync gate (5/8 sync symbols decided on a frame whose payload was valid). Attempt 2 (this file) fixes the validator (bytes-aware content comparison + LXMF message-hash equality) and relaxes the sync gate to >= 5/8, with RS + length + CRC-32 remaining the sole arbiters of frame validity. All gated numbers above are from attempt 2, run end-to-end after the fixes.

## Honest scope
Baseband audio + a simulated channel model; **no RF was emitted** and nothing was transmitted over the air. What crossed the simulated channel in this test is the complete packed LXMF packet itself (unlike the FT8 beacon test, where only message content crossed as a token). The remaining physical step is unchanged: feed this modem's audio to a real SSB transmitter / receive it on a real receiver, which requires licensed hardware.
