# TX_PACKAGE.md — 5-Minute Operator Brief: First On-Air Test

**For:** the licensed control operator (Pakistani amateur / PARS club
station) who has kindly agreed to transmit a one-time test beacon.
**Prepared by:** Nature-Mirror Mesh research project (Muhammad Imran,
student researcher, unlicensed — he will not touch the equipment; the
transmission is yours, under your callsign, logged by you).
**What it costs you:** about 60 seconds of airtime, once.

---

## What you are transmitting (exactly)

Mode: **FT8** (WSJT-X or compatible), USB, standard FT8 watering holes:

- **Primary: 14.074 MHz (20 m)** — dial frequency, audio offset your usual
  ~1,000–1,500 Hz
- **Alternate: 7.074 MHz (40 m)** — if 20 m is dead at the agreed time

Sequence — **4 consecutive 15-second FT8 slots (60 s total)**, starting on
a slot boundary. Slots 1 and 4 are your own normal identification; slots
2–3 are the test payload (a proven format — see "Why these texts" below):

| Slot | Transmit this text | Purpose |
|---|---|---|
| 1 | `CQ <OPERATOR_CALLSIGN> <OPERATOR_GRID>` | Your normal CQ — station identification |
| 2 | `CQ ZD9ULB PE01` | Test beacon, part 1 |
| 3 | `ZD9ULB SE7SIT PE02` | Test beacon, part 2 |
| 4 | `CQ <OPERATOR_CALLSIGN> <OPERATOR_GRID>` | Identification again, closing the sequence |

In WSJT-X: set each line as the TX message for successive periods
(TX1–TX4 style sequencing, or free-text/standard-message entry per slot).
The two payload texts are valid standard-format FT8 messages (the
"callsigns" in them are data tokens shaped as callsigns — that is the
documented, publicly-known encoding, not a false identity claim: your
real callsign brackets the sequence in slots 1 and 4 and appears in your
log as the transmitting station).

**Power:** the lowest that serves — FT8 is a weak-signal mode; **10–25 W**
into your normal antenna is ideal for a test. Never exceed your license
or station limits; 100 W is an absolute ceiling, not a target.

**Worked example already proven in simulation:** the pair above carries
the check token **`NMM-TX-ZD9ULBSE7SIT`**. For the real test we will
generate a **fresh** token pair the same way and hand it to you in
advance (same shapes: chunk = `[A-Z][A-Z][0-9][A-Z][A-Z][A-Z]`, grid =
2 checksum letters + `01`/`02`). Nothing about the format changes.

## Why these texts (the one-line explanation)

> This is a one-time technical test transmission for the Nature-Mirror
> Mesh offline-messaging research project: two 15-second FT8 messages
> carry a 12-character **plaintext** check token (`NMM-TX-…`) so that
> distant receivers and PSK Reporter can confirm the signal crossed the
> ionosphere — the token and its encoding are publicly documented, and
> there is **no encrypted content** of any kind.

(If anyone on frequency asks: it is a student research propagation test,
transmitted by you as control operator; the token decodes with the
project's published mapping — any FT8 receiver can read the raw texts
with ordinary WSJT-X.)

## Agree before the day (2 minutes)

1. **Date/time window (UTC)** and band choice (20 m primary / 40 m
   alternate), chosen against that day's propagation.
2. You receive the **fresh token pair** (slots 2–3 texts) from us in
   writing before the test.
3. We monitor independently: live KiwiSDR/WebSDR receivers + **PSK
   Reporter** — if your signal is spotted, we will see your callsign's
   spots and the beacon decodes without you doing anything extra.

## Please report back afterwards (any format — a photo of the screen is fine)

- Date and **UTC start time** of slot 1
- **Dial frequency** and audio offset used; band actually used
- **Power** (watts) and antenna (type/height if handy)
- The **exact four texts** as transmitted
- Anything you decoded or were called by during/after the sequence
- Your WSJT-X log line / screenshot if available
- Anything unusual (QRM, band conditions as you judged them)

We will add: PSK Reporter spots for your callsign (who heard you, where,
SNR), any KiwiSDR recordings that decode the pair, and the reconstructed
token — and send you the complete report for your log and for PARS.

## Legal notes (read once — 20 seconds)

- **Plaintext only.** The beacon texts are ordinary FT8 messages that
  anyone can decode; the token mapping is published in the project repo.
  No encryption, no hidden meaning beyond the documented check token —
  compliant with the amateur-service prohibition on encryption/codes
  meant to obscure meaning.
- **Your callsign, your control.** You are the control operator; the
  station identifies with your callsign (slots 1 and 4 and your log).
  Muhammad Imran is unlicensed and will not operate the transmitter in
  any way; he supplied only the text of a technical test, which you
  transmit (or decline to transmit) entirely at your discretion, in line
  with the Amateur Radio Services Regulations 2004 (plain-language
  technical/propagation traffic; non-commercial; no pecuniary interest).
- **Log it** as a test transmission ("beacon test for student research
  project Nature-Mirror Mesh") with time/frequency/power as above.
- If band conditions, QRM, or your own judgment say "not today" — we
  reschedule, no questions asked. You are doing us a favour.

*Format provenance: the beacon pair and checksum mapping are from the
project's transmission-chain test (`lab/tx_chain_test.py`), where this
exact pair was recovered error-free through a simulated Watterson HF
channel at −5, −10 and −15 dB and with a +30 Hz offset. The receive half
of this test (real off-air FT8 decoded from public receivers) has
already been demonstrated by the project; this transmission is the
missing half.*
