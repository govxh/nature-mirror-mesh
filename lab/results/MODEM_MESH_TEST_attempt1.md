# Multi-Hop Mesh over Modem Links — Results (DIGITAL LAB 2)

Date (UTC): 2026-10-20 10:09

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

## Per-hop statistics

| Hop | Frames TX | RX ok | RX fail (lost) | Distinct packets | Retransmitted frames | Simulated airtime | Max packet |
|---|---|---|---|---|---|---|---|
| S->T | 13 | 8 | 5 | 13 | 0 | 300.7 s | 227 B |
| T->C | 18 | 12 | 6 | 12 | 6 | 640.7 s | 244 B |
| C->T | 18 | 12 | 6 | 18 | 0 | 750.8 s | 228 B |
| T->S | 17 | 12 | 2 | 10 | 7 | 707.6 s | 244 B |

Total simulated airtime: 2399.8 s; wall clock (sender phase): 249 s; maximum RNS packet seen on any interface: 244 B.

## Evidence at C

- Token sent by S: `NMM-MODEMMESH-D2F919DTL06M`
- Token received at C: `None`
- LXMF hash at S: `a2b4e44d73d6e61dc7af9c04e9c2c70bbea497167471ac7cc79bb01f2a8710a4`
- LXMF hash at C: `None`
- LXMF packed size: 151 B
- S hops_to(C): 2; T hops_to(C): 1
- LXMF delivery_attempts at S: 5 (criterion <= 3)
- S router reached DELIVERED state: False (the LXMF proof crossed both hops back)

## Verdict

**FAIL** — against the pre-registered criterion above.

## Honest scope
Baseband audio + simulated channel models only; **no RF was emitted**, nothing was transmitted over the air, and no TCP/UDP link exists between the nodes — the spool files carry post-channel audio, nothing else. Simulated airtime is the duration the frames would occupy on a real ~40 bit/s HF link; the lab machines exchange them at CPU speed, so wall-clock time is much shorter. The remaining physical step is unchanged: real radios and licensed spectrum.
