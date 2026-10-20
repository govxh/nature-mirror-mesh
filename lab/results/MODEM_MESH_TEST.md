# Multi-Hop Mesh over Modem Links — Results (DIGITAL LAB 2)

Date (UTC): 2026-10-20 10:12

## Question
DIGITAL LAB 1 proved a full LXMF packet crosses ONE simulated Watterson hop via nmm_modem; the phase-2 mesh test proved Reticulum transport forwarding S -> T -> C over TCP. Can the two be combined — a three-node mesh where EVERY link is the modem over a simulated HF channel, with no TCP anywhere?

## Implementation tier achieved
**Tier (1) — custom Reticulum Interface.** lab/modem_interface.py subclasses RNS.Interfaces.Interface.Interface and is loaded by each node through Reticulum's external-interface mechanism (config `type = ModemInterface`, module in <configdir>/interfaces/). Outgoing RNS packets are modem-encoded, passed through the Watterson channel and spooled as WAV frames; the peer interface demodulates them into Transport.inbound. Announce, path and proof traffic cross the modem links exactly like data. No fallback to an application-level relay was needed.

## Pre-registered criterion
PASS = C's LXMF layer validates the message (content == token AND LXMF hash == sent hash) after traversing both modem hops at -10 dB per hop, within 3 end-to-end (LXMF) attempts; S hops_to(C)==2 and T hops_to(C)==1. Stated in the test header before any run.

## Design
- Nodes: S (sender), T (transport, enable_transport=True), C (receiver) — separate processes, separate Reticulum config dirs, the ONLY interfaces are ModemInterface instances.
- Medium: one spool directory of WAV frames per directed hop (S->T, T->S, T->C, C->T). The transmitting interface applies the channel (tx_chain_test.apply_channel: two paths 0.5/2.0 ms, powers 0.6/0.4, Rayleigh envelopes, Doppler sigma 0.7 Hz, AWGN) at -10 dB with a per-link, per-frame seed; the file on disk is the post-channel audio.
- Fragmentation: none needed — see stats (max RNS packet vs 4096 B modem frame capacity; frames-per-packet = 1).
- Link-level repetition: every frame is transmitted 3x (frame_repeats = 3), each copy through an independent channel seed; the receiver injects every copy that decodes and RNS dedups the extras. Added after run 1, where the data packet's single hop-2 forward was lost (per-frame loss ~1/3 at 200-244 B, -10 dB) and LXMF end-to-end retransmission could not recover it. The 'Retransmitted frames' column counts these deliberate repetitions plus any stack-level retransmissions; all are included in airtime.

## Per-hop statistics

| Hop | Frames TX | RX ok | RX fail (lost) | Distinct packets | Retransmitted frames | Simulated airtime | Max packet |
|---|---|---|---|---|---|---|---|
| S->T | 18 | 9 | 3 | 6 | 12 | 530.6 s | 227 B |
| T->C | 21 | 18 | 3 | 5 | 16 | 742.9 s | 244 B |
| C->T | 15 | 11 | 1 | 5 | 10 | 524.8 s | 228 B |
| T->S | 27 | 21 | 6 | 5 | 22 | 1002.4 s | 244 B |

Total simulated airtime: 2800.7 s; wall clock (sender phase): 26 s; maximum RNS packet seen on any interface: 244 B.

## Evidence at C

- Token sent by S: `NMM-MODEMMESH-ARGV8PP598JR`
- Token received at C: `NMM-MODEMMESH-ARGV8PP598JR`
- LXMF hash at S: `1a827d8f58ef5a646317e8d670231a1c25d102d321c5adab55d3eca9eaa84509`
- LXMF hash at C: `1a827d8f58ef5a646317e8d670231a1c25d102d321c5adab55d3eca9eaa84509`
- LXMF packed size: 151 B
- S hops_to(C): 2; T hops_to(C): 1
- LXMF delivery_attempts at S: 1 (criterion <= 3)
- S router reached DELIVERED state: True (the LXMF proof crossed both hops back)

## Verdict

**PASS** — against the pre-registered criterion above.

## Honest scope
Baseband audio + simulated channel models only; **no RF was emitted**, nothing was transmitted over the air, and no TCP/UDP link exists between the nodes — the spool files carry post-channel audio, nothing else. Simulated airtime is the duration the frames would occupy on a real ~40 bit/s HF link; the lab machines exchange them at CPU speed, so wall-clock time is much shorter. The remaining physical step is unchanged: real radios and licensed spectrum.
