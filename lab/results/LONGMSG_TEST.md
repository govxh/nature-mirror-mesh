# Long Messages over the Radio Mesh — Results (DIGITAL LAB 3, Part 1)

Date (UTC): 2026-10-20 10:54

## Question
DIGITAL LAB 2 delivered a short LXMF message (151 B packed) over a two-hop mesh whose every link is the nmm_modem over a simulated Watterson HF channel at -10 dB per hop. What message sizes can that mesh actually carry? This test sends LXMF messages with content of 500 B and 1500 B over the identical setup and measures the envelope honestly.

## Pre-registered criterion
PASS (per size) = delivery with content bytes AND LXMF message hash validated at C (content SHA-256 match, LXMF hash match, length match) within 2 end-to-end attempts (fresh node trio per attempt). OVERALL PASS = both sizes pass. If a size fails both attempts, a descent (1000 B, then 750 B) finds the largest passing size. Stated in the test header before any run.

## Design
- Identical to DIGITAL LAB 2: nodes S/T/C as separate processes whose ONLY interfaces are ModemInterface (nmm_modem 16-FSK + RS over the Watterson channel, frame_repeats = 3, -10 dB per hop, spool-directory 'air'). No TCP/UDP anywhere.
- Content: exact-length bytes — ASCII header `NMM-LONGMSG-<size>B-` + seeded pseudo-random bytes (seed fixed per size; reproducible).
- Larger payloads are handled by LXMF/Reticulum natively (link + resource transfer once a message outgrows the single-packet path); nothing is special-cased.

## Measured envelope

| Content size | Attempt | Result | Wall clock | Simulated airtime | Frames TX (all hops) | Retrans. frames | LXMF delivery attempts | Packed len | Max RNS pkt |
|---|---|---|---|---|---|---|---|---|---|
| 500 B | 1 | PASS | 31.4 s | 3142.6 s | 87 | 61 | 1 | 623 B | 483 B |
| 1500 B | 1 | PASS | 31.0 s | 4463.5 s | 108 | 76 | 1 | 1623 B | 483 B |

## Verdict

**PASS** — both 500 B and 1500 B delivered with content + hash validated at C within the pre-registered attempt budget. Measured envelope: at least 1500 B content per message over 2 simulated-radio hops at -10 dB per hop.

## Honest scope
Baseband audio + simulated channel models only; **no RF was emitted**, nothing was transmitted over the air, and no TCP/UDP link exists between the nodes. Simulated airtime is the duration the frames would occupy on a real ~40 bit/s HF link; wall clock is CPU time and is much shorter. The remaining physical step is unchanged: real radios and licensed spectrum.

## Debugging record — the failed attempts that preceded this PASS (preserved, not hidden)

The table above is the official run. Getting there took a debugging arc
that is part of this lab's evidence and is recorded here in full.

**Symptom (3 consecutive 500 B attempts, 2026-10-20 ~10:12–10:26 UTC):**
every attempt scored FAIL with `content_ok=False, hash_ok=False` at the
orchestrator — yet the sender reached LXMF state **DELIVERED** on
delivery attempt 1 (packed 623 B, S hops_to(C)=2), and the receiver's
log showed the resource transfer "concluded". No error was logged
anywhere. The receiver's delivery callback simply never fired.

**Diagnosis (instrumented runs, loglevel 7 + wrappers on
`LXMRouter.delivery_resource_concluded` and `RNS.Resource.assemble`):**
the LXMF callback DID fire — with `resource.status = 3`
(TRANSFERRING) instead of 6 (COMPLETE), so LXMF's status check
silently skipped delivery. Stack trace placed the call inside
`RNS/Resource.py:751` (`assemble()` → callback), i.e. the genuine
assembly path. Root cause: a race between RNS and this lab's
interface. `Resource.assemble()` runs on its own thread: it validates
the hash, sets status COMPLETE, sends the proof (which is why the
sender saw DELIVERED), and only then invokes the app callback.
`Resource.receive_part()` meanwhile sets `status = TRANSFERRING`
unconditionally on **every** part packet it is handed — and with
`frame_repeats = 3` on both hops, duplicate copies of the resource's
parts were still draining out of the spool and being injected while
assembly ran. One duplicate landing in the prove→callback window
reverted the status to TRANSFERRING and the assembled message was
dropped without a trace. Single-packet messages (DIGITAL LAB 2,
151 B) usually won this race; the 2-part 688 B resource reliably
lost it.

**Fix (interface layer, `lab/modem_interface.py`):** duplicate
suppression — the interface now injects each distinct packet payload
at most once per 300 s window (exact-payload SHA-256); later copies
are counted as `rx_dup` and dropped. A real interface never delivers
the same packet repeatedly; RNS assumes it doesn't. Loss protection
is unchanged (suppression starts only after a copy has decoded and
been injected). Instrumented re-run after the fix:
`assemble enter status=3 → delivery_resource_concluded status=6
(COMPLETE) → ATTEMPT: True True True`. The fix also cut the 500 B
simulated airtime from 7,564.9 s (unfixed debug run) to 3,142.6 s,
because transport nodes no longer re-forward duplicate cascades.

**Lesson for the app phase:** when an interface can deliver duplicate
packets (any repeated/relayed medium), dedup belongs at the interface,
below RNS — otherwise large (multi-part resource) messages can be
silently dropped even though every layer reports success.
