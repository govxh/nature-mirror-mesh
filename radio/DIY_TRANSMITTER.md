# DIY_TRANSMITTER.md — Build Your Own Transmitter (the self-reliance route)

**For:** Muhammad Imran — this is the route where Nature-Mirror Mesh
depends on **nobody**: your own PTA license (in progress via the PARS
SWL route, see `FIRST_TX_ROUTES.md`) + a transmitter you built with
your own hands, driven by this project's own signals.
**Status of this document:** a build dossier, prepared 2026-10-20.
Nothing here has been built yet — every design below is an established,
published homebrew design with sources, and every price is an
**ESTIMATE** (see the note on prices). Read the legal section (§4)
before connecting anything to an antenna.

> **Prices — read this first.** Every rupee figure in this document is
> an **ESTIMATE**, gathered 2026-10-20 from public listings (Daraz.pk,
> epro.pk, AliExpress/Shenzhen supplier listings, QRP Labs list
> prices). Electronics prices in Pakistan move with the dollar and with
> stock. Nothing here is a confirmed quote — treat the totals as
> "order of magnitude for planning", and re-check the actual shelf
> price (Hall Road, Lahore; Shah Alam; or online) on the day money is
> spent.

---

## 1. Primary design — Si5351 FT8/WSPR beacon transmitter

### 1.1 The idea in one paragraph

A normal transmitter builds its radio signal with a big oscillator and
mixers. We skip all of that. The **Si5351A** is a programmable clock
chip (about the size of a fingernail, controlled over I²C by any
microcontroller) that can output a clean square wave at *any*
frequency from 8 kHz to ~160 MHz, adjustable in steps far finer than
1 Hz. FT8 and WSPR are nothing but a carrier that hops between a few
closely-spaced tones in a precise rhythm — and a chip that can be told
"now be at 14,074,000 Hz, now 6.25 Hz higher, now 12.5 Hz higher…" can
*be* an FT8/WSPR transmitter all by itself. A microcontroller (Arduino
Nano or ESP32) runs the **JTEncode** library (by Jason Milldrum,
NT7S — the standard open-source encoder for JT65/JT9/FT8/WSPR/FSQ),
which turns a message into the exact symbol/timing sequence, and steps
the Si5351 through the tones. Add a low-pass filter (mandatory), and
that is a complete, real digital-mode transmitter.

Two ways this connects to **our** system:

- **Standalone (this dossier's main path):** the microcontroller
  generates the tones directly. No PC, no sound card, no SSB rig. Our
  proven beacon texts (the `CQ ZD9ULB PE01` / `ZD9ULB SE7SIT PE02`
  pair from `lab/tx_chain_test.py`, documented in `TX_PACKAGE.md`)
  are *standard-format FT8 messages* — exactly what JTEncode's FT8
  encoder accepts. The fresh-token procedure in `TX_PACKAGE.md`
  applies unchanged; only the box that speaks them changes.
- **Driven by our app/lab (later, optional):** our software already
  generates finished FT8 **audio** (via ft8_lib — proven in the lab
  and over the simulated channel). Audio cannot drive a bare Si5351 —
  a clock chip has no way to "play" a waveform; audio needs a proper
  SSB transmitter to carry it (e.g. a QRP Labs QMX-class digital rig,
  ~US$65 kit — a possible *later* purchase, not part of this build).
  For a from-scratch build, direct synthesis (above) produces the
  same class of on-air FT8 signal with a fraction of the hardware, so
  that is the route documented here.

One honest technical note: JTEncode + Si5351 produces *tone-stepped*
FT8/WSPR rather than textbook Gaussian-filtered FT8. This is the
approach used by a large, long-running family of published beacons
(the Etherkit app notes, the "Classie" transmitter, the QRP Labs
Ultimate series ecosystem) and WSJT-X/WSPR decoders receive it
normally. It is a beacon, not a hi-fi signal — and a beacon is what
this project needs.

### 1.2 The signal chain

```
 Nano/ESP32 ──I²C──► Si5351A module ──► [BS170 buffer, ~1 W] ──► [IRF510 PA, ~5 W] ──► LPF (per band) ──► antenna
 (JTEncode)            ~10 mW              optional stage A          optional stage B        mandatory
```

Each bracketed stage is optional and can be built later; the chain is
designed to grow. FT8 and WSPR are **constant-envelope** modes (the
carrier never changes amplitude, only frequency), so the amplifiers
do **not** need to be linear — cheap, efficient switching (class-C/E)
stages are legitimate here, unlike SSB voice. That one fact is what
makes a student-budget transmitter possible at all.

**Timing is part of the signal.** FT8 transmits 79 symbols × 0.16 s =
12.64 s, starting exactly on 15-second UTC slot boundaries. WSPR
transmits 162 symbols over 110.6 s, starting on even UTC minutes. A
bare Nano's ceramic resonator drifts too much to hold slot timing for
long, and the Si5351's cheap 25 MHz reference crystal can be off by
tens of ppm (hundreds of Hz at 14 MHz) — both are *calibration*
problems with known fixes, handled in the build order (§3, stage 4):
a GPS module (its 1 PPS pulse nails both time and, by counting,
frequency) is the robust answer and is listed as an early option;
for bench work into a dummy load, none of it matters yet.

### 1.3 What the bare Si5351 can actually do — honestly

- **Output:** ≈ **+10 dBm ≈ 10 mW** (builders measure ~7–13 mW /
  "12-ish milliwatts" straight from the chip, 8 mA drive setting,
  into 50 Ω after the mandatory LPF). [Hackaday, *Careless WSPR*
  project log; Etherkit App Note on a 10 mW WSPR beacon.]
- **On WSPR:** 10 mW is a *real* signal, not a toy. WSPR decodes down
  to about −28 dB SNR and exists precisely for this. With a proper
  full-size antenna (see §1.6) up reasonably high and the band open,
  10 mW WSPR transmissions are routinely spotted across continents and
  logged publicly on WSPRnet — Jason NT7S's published app note builds
  exactly this (Si5351 board + low-pass filter, nothing else). What
  10 mW WSPR gets you: proof your antenna works, a live map of where
  your signal reaches, and propagation data for the oracle — but
  **WSPR's payload is only callsign + grid + power. It cannot carry
  our chat tokens.** It is a path-prover, not the message carrier.
- **On FT8 (our token format):** be sober. FT8 decodes to about
  −20 dB SNR — excellent, but the FT8 watering holes are full of
  5–100 W stations. At 10 mW, FT8 decodes happen at regional range
  (hundreds of km) on a good, open band with a good antenna;
  intercontinental FT8 at 10 mW is the exception, not the plan.
  **Practical floor for our FT8 token test: the ~1 W stage (§1.4).**
  1 W of FT8 on 20 m in decent conditions commonly makes
  1,000–3,000 km; 5 W makes the test comfortable rather than hopeful.

### 1.4 Amplifier options (build in this order, stop when satisfied)

**Stage A — BS170 buffer, ~1 W (build this first).** One BS170
MOSFET, gate driven straight from a Si5351 clock output (optionally
through a 74HC-series logic buffer), run as a class-C/E switcher on
12 V. This is the published "Classie" WSPR transmitter topology
(KC3XM, written up by NT7S): measured **≈1 W RF out for ≈1.2 W DC
in**, running cool — remarkable efficiency from one transistor that
costs less than a cup of chai. Three BS170s in parallel (the QRP Labs
QCX arrangement) at 12–13.8 V is the same idea scaled to ~3–5 W if a
single device runs hot on the lower bands.

**Stage B — IRF510 PA, ~5 W (the "proper" PA, optional).** The QRP
Labs 5 W HF PA design (Hans Summers, G0UPL): a **single IRF510**,
≈16 dB gain, ~5 W out on 13.8 V, needs ≈200 mW of drive — i.e. it
sits *after* Stage A (pad Stage A down to ~200 mW) or after a
dedicated driver. QRP Labs sells it as a kit (listed at US$20 in
their Jan 2017 newsletter; check current price) including a big
heatsink and an optional raised-cosine envelope shaper — the shaper
is for CW key-clicks and can be omitted for FT8/WSPR (use their
published *simplified assembly*). Scratch-building the same circuit
from parts is equally legitimate. Rules that are not optional:
heatsink fitted, gate bias set with the multimeter before first
power, **always** followed by the band LPF, **never** keyed without
a dummy load or antenna attached.

### 1.5 Low-pass filters — mandatory, per band, exact values

The Si5351 outputs a **square wave**: rich in odd harmonics. Without
a filter you would radiate on 2×, 3×, 5×… your frequency — illegal
and antisocial. A filter is not an accessory; it is part of the
transmitter. Use the published **G-QRP / W3NQN 7-element Chebyshev**
design exactly as tabulated in the free QRP Labs *Low Pass Filter
Kit* assembly manual (C0G/NP0 ceramic capacitors only — ordinary
ceramic discs drift and lossy ones melt at 5 W):

| Band | C1 = C4 | C2 = C3 | L1 = L3 | L2 | Toroids (all three) |
|---|---|---|---|---|---|
| **40 m** | 270 pF | 680 pF | 21 turns ≈ 1.38 µH | 24 turns ≈ 1.70 µH | T37-6 (yellow) |
| **20 m** | 180 pF | 390 pF | 16 turns ≈ 0.77 µH | 17 turns ≈ 0.90 µH | T37-6 (yellow) |

Topology: C1 shunt → L1 series → C2 shunt → L2 series → C3 shunt →
L3 series → C4 shunt, 50 Ω both ends. Wind with ~0.4–0.5 mm enamelled
wire, turns spread over ~¾ of the core, count a "turn" as each pass
through the hole. One filter per band; swap by connector, or build
both on one board with a switch later. (Source: QRP Labs LPF kit
manual, qrp-labs.com — the same values appear in their QCX manuals.)

### 1.6 Antenna — the other half of the transmitter

Everything this project has *received* came through other people's
antennas; transmission makes the antenna your problem. At these
powers the antenna matters more than the amplifier — **spend effort
here before spending money on watts.**

- **40 m half-wave dipole (simplest, recommended first):** two legs
  of ≈10.1 m wire each (468 ÷ 7.074 MHz ≈ 66 ft total), fed in the
  centre with 50 Ω coax (RG-58), centre hung as high as possible
  (rooftop, tree, PVC-pipe mast), legs out flat or as an inverted-V.
  No balun is strictly required at QRP to start; a few turns of the
  coax itself in a coil at the feedpoint makes a serviceable choke.
- **20 m half-wave dipole:** two legs of ≈5.1 m each — small enough
  for almost any rooftop; this is the daylight DX band for the token
  test.
- **End-fed half-wave (EFHW), later:** one ~20 m wire for 40 m (also
  works on its harmonics incl. 20 m) fed at the end through a 49:1
  unun (2:14 turns on an FT140-43 toroid) — one high support only,
  the classic one-tree antenna. The unun toroid is its one
  hard-to-scavenge part.
- Wire: ordinary multi-strand copper electrical wire works (insulated
  is fine); supports from rope/paracord; keep the wire away from
  metal roofs and power lines, and **never** where a fallen wire
  could touch a power line. Height and clear space beat exotic
  designs at every power level in this document.

### 1.7 Parts list — primary design (all prices ESTIMATES, 2026-10-20)

| # | Part | Notes | Est. PKR | Source of estimate |
|---|---|---|---|---|
| 1 | Si5351A breakout module | Generic CJMCU/Adafruit-style w/ 25 MHz crystal + level shifting. The one part with no substitute. | 1,200–2,500 | AliExpress module listings US$0.85–5.20; Adafruit US$7.95; QRP Labs synth module US$7.50 — landed-PK estimate; no PK retail listing confirmed |
| 2 | Arduino Nano (clone) **or** ESP32 dev board | Nano = simplest JTEncode path (5 V, huge example base). ESP32 = built-in Wi-Fi for NTP time sync; pick one. | Nano 1,200–1,500 · ESP32 1,400–1,800 | epro.pk Nano listing Rs 1,300 · Daraz ESP32 listings Rs 1,378–1,785 |
| 3 | GPS module, NEO-M8N class *(Stage-2 option — timing/frequency discipline, §3 stage 4)* | Skip for bench phase; buy before any on-air plan. | 2,000–3,500 | International module prices ~US$8–15, landed estimate; no PK listing confirmed |
| 4 | BS170 MOSFET ×3 | Stage A + spares (beginners kill MOSFETs; buy spares). | 150–400 total | Commodity small-parts estimate, Hall Road class |
| 5 | IRF510 MOSFET *(Stage B option)* | + mica insulator + heatsink (scavengeable, §1.8). | 100–300 | Commodity estimate |
| 6 | LPF parts, per band: 3× T37-6 toroids, 4× C0G caps (values §1.5), ~2 m 0.5 mm enamelled wire | Toroids are the fiddliest item to source locally; QRP Labs sells the complete LPF kit if stuck (US$~5 class + post). | 400–800 / band | Small-parts estimate |
| 7 | Connectors & board: BNC or SMA female ×2, perfboard/copper-clad offcut, hookup wire | Ugly-construction on a copper-clad offcut is the classic RF-correct method (solid ground plane). | 600–1,000 | Small-parts estimate |
| 8 | Power: 12 V / 2 A adapter + 7805 or buck module for 5 V rail | Almost always scavengeable (§1.8). | 0–600 | Daraz buck module listed Rs 150 |
| 9 | Enclosure: metal tin / salvaged box | Metal = RF shielding + heatsinking. | 0–500 | Scavenge-first |
| 10 | Antenna wire ~25 m + rope + insulators (plastic offcuts) | For the 40 m dipole; 20 m needs ~12 m. | 800–1,500 | Wire-shop estimate |

**Stage-1 total (Si5351 + controller + one band's LPF + small parts,
scavenged PSU/enclosure): ≈ PKR 3,500–6,000 — ESTIMATE.**
Full growth path (+ BS170 stage, + GPS, + IRF510 stage, second band):
**≈ PKR 9,000–15,000 — ESTIMATE**, spread over months, each stage
independently testable and useful. For comparison so this stays
honest: a Pixie kit (§2) is cheaper than Stage 1 but does a different,
smaller job; and the eventual licence itself is ≈ PKR 5,000 over its
own timeline (`FIRST_TX_ROUTES.md`).

### 1.8 Scavenging list — what dead electronics can donate

| Wanted | Where it hides | Honest caveat |
|---|---|---|
| 12 V / 5 V power supplies | Dead routers, CCTV DVRs, laptop bricks, printer adapters | Measure actual voltage with the multimeter before trusting the label; tired adapters sag under load |
| Heatsinks | PC power supplies, dead motherboards/GPUs, old audio amps | Perfect for the IRF510; drill + mica/thermal pad from the same corpse |
| Enamelled copper wire | Dead motors, transformers, ceiling-fan coils, relay coils | Ideal for winding LPF toroids; unwind gently, it's free and exactly the right stuff |
| Toroids (iron powder) | PC PSUs contain yellow/white toroids (−52 material) | Usable for a *first* LPF at 40 m with adjusted turns, but the mix differs from T37-6 (−6) — treat as experimental; the EMI ferrite cores in PSUs/cables are for chokes/unun experiments, not precision filters. Buy real T37-6s if the filter misbehaves |
| MOSFETs | UPS boards (IRF-series appear here), SMPS | Motherboard VRM MOSFETs are low-voltage parts — **not** substitutes for IRF510 at 12 V drain service. Test any salvaged MOSFET with the multimeter diode range before use; keep expectations low, spares are cheap (§1.7 #4/#5) |
| Metal enclosures | Biscuit/tea tins, dead DVD players, PSU cases | A biscuit tin is the traditional QRP enclosure, unironically |
| Coax | Old CCTV installs (RG-59, 75 Ω) / network-era RG-58 | RG-58 (50 Ω) preferred. RG-59 works at QRP with a small mismatch penalty — fine for receiving checks, acceptable for a first dipole at these powers |
| LM386, small transistors (9018/2N3904 class), resistors, caps, crystals (misc) | Dead radios, toys, TV boards — the Pixie's whole bill of materials (§2) | The one Pixie part you will likely have to *buy* is the 7.023 MHz crystal |
| PVC pipe, rope, wire | Construction leftovers | Mast + antenna hardware for free |

---

## 2. The ultra-cheap alternative — the Pixie (build this too, or first)

The **Pixie** is the most-built first transmitter in amateur radio
history, and the correct answer to "what can I possibly build with
almost nothing?" Lineage: the power-amplifier-transistor-as-mixer
trick comes from GM3OXX's FOXX (SPRAT, 1983); Oleg Borodin, RV3GM,
distilled it into the 4-transistor **Micro-80** (SPRAT, 1992); the
**Pixie 2** (WA6BOY, 1995) replaced two transistors with an LM386
audio chip, and today's ubiquitous ~US$10–15 Chinese kits are that
circuit: a crystal oscillator (fixed **7.023 MHz**), one transistor
that is PA on transmit and mixer on receive, an LM386 for the
headphones. **~0.8 W out on 9 V, ~1.2 W on 12 V**, CW (Morse) only,
keyed by any switch.

Why build it, given it can't carry FT8 or our tokens?

- It teaches the entire transmit chain — oscillator, PA, low-pass
  filter, keying, dummy load — in one evening, for the price of a
  pizza, with parts that are all scavengeable except the crystal.
- Its **receiver works from day one, license-free** (§4): build it,
  connect the §1.6 dipole, and you can *hear* 40 m CW activity —
  your antenna's first real test, and your first ear-training for
  the band our beacon will live on.
- CW at ~1 W is not a toy either: published Pixie reports include a
  559 report from western Kansas for a half-watt Michigan Pixie
  (CQ Magazine, Feb 2018). It gets out — with a human copying Morse
  at the other end, which is also its limitation: **a person, not a
  machine, must be listening.** It cannot run the project's token
  protocol; the Si5351 rig can. Build the Pixie for skill and for
  its receiver; build the Si5351 for the mission.

Honest flaws, so there are no surprises: the kit's harmonic
suppression is specified at only −20 dB (poor — its little π filter
is minimal; do not "improve" power without improving filtering), the
receiver is broad and unselective, and there is no sidetone. It is a
first rung, priced and sized like one. (Kit sources: AliExpress
~US$15 class — ESTIMATE PKR 3,500–5,500 landed; from loose parts,
less, if a 7.023 MHz crystal can be found.)

---

## 3. Build order — everything testable license-free, on a dummy load

**The dummy load comes first and is never skipped.** Build it before
anything else: two 100 Ω / 2 W resistors in parallel (= 50 Ω, 4 W)
soldered across a BNC/SMA connector inside a small metal tin, or a
short coax tail ending in the resistors. Every stage below is tested
**into the dummy load only**. A dummy load converts your RF to a
tiny amount of heat in a resistor instead of radiating it — the
entire bench phase is receive-only as far as the outside world is
concerned.

**Your one measurement instrument** (beyond the multimeter) is an
**RF probe**: a 1N4148 (or any small signal diode), a 4.7 nF
capacitor and a 100 kΩ resistor in a dead pen tube — rectifies RF to
a DC voltage the multimeter can read. It can't tell you frequency or
absolute watts, but it truthfully answers "is RF present, and is it
bigger/smaller than before?" — which is 90 % of bench debugging.
Reference points into 50 Ω (probe reads ≈ peak volts): 10 mW ≈
2.0 Vpp ≈ probe ~0.9 V DC · 1 W ≈ 20 Vpp ≈ ~6.7 V DC · 5 W ≈
44.7 Vpp ≈ ~15.5 V DC (after the diode drop; treat as relative).

| Stage | Build / do | Bench check (dummy load only) |
|---|---|---|
| **0. Prep** | Dummy load + RF probe built; PSU rails measured (12 V and 5 V present, correct polarity — mark it with tape) | Multimeter only. No RF exists yet |
| **1. Controller alive** | Nano/ESP32 programmed: blink test, then load Si5351Arduino + JTEncode libraries, run an I²C scan | Scan finds the Si5351 at address **0x60**. If not: wiring/level-shifting, not RF — fix here, cheap |
| **2. Si5351 alone** | CLK0 → (through the §1.5 LPF, build the 40 m one now) → dummy load. Set 7.074 MHz CW carrier from a test sketch | RF probe shows RF present; supply current sane (tens of mA). Touch test: Si5351 module merely warm |
| **3. Waveform sanity** | Run a JTEncode **WSPR** test sequence into the dummy; watch the probe needle: WSPR's continuous 110 s carrier should sit rock-steady; then an **FT8** sequence: 12.64 s on, off at slot end | Confirms the *timing code* works end-to-end. Log start/stop against a phone clock — drift visible here is the Stage-4 problem announcing itself |
| **4. Calibration** (the stage beginners skip and regret) | Measure/correct (a) **slot timing**: GPS 1 PPS is the clean fix (module from §1.7 #3); interim: sync the controller clock from the PC/phone at session start and keep sessions short. (b) **frequency offset**: the Si5351 library takes a correction factor (ppb). Determine it by *one borrowed-receiver afternoon* (any HF rig / RTL-SDR / a club member's station, receiving your dummy-load leakage at 1 m distance is enough at these powers — or better, their signal generator discipline) and hard-code it | Write the measured correction in the sketch header with the date. **Until this stage is done, the rig is a bench instrument, not a transmitter** — an uncalibrated beacon pollutes the waterfall and fools nobody |
| **5. Stage A (BS170)** | Add the BS170 stage between Si5351 and LPF. First power with a 12 V **bulb in series** as a sacrificial current limiter | Key-down 10 s into dummy: probe should jump to the ~1 W region; current ≈ 100–200 mA class; BS170 warm, not painful. If the bulb glows bright at idle: bias/wiring fault — power off, think |
| **6. Pixie (parallel track)** | Build the Pixie; test TX side into dummy only (same probe checks); then use its **receiver** with the real antenna | You should hear live 40 m CW in the headphones in the evening — antenna verified, license-free, and the project's first *own-hardware* reception |
| **7. Stage B (IRF510, optional)** | Heatsink + mica on; bias preset to minimum; bulb limiter in; raise bias to the QRP Labs simplified-build idle figure (~tens of mA) | Staged key-downs (2 s → 10 s → 30 s) into dummy, heatsink temperature by careful touch, probe trending to ~5 W. Any oscillation symptom (current jumps, probe flicker with no key) = stop, add decoupling, shorten leads |
| **8. Full dress rehearsal** | Whole chain, final band LPF fitted. Run the complete `TX_PACKAGE.md` 4-slot FT8 sequence + a WSPR frame into the dummy, timed | Everything logged (currents, probe readings, timings) in a notebook page = the rig's birth certificate. **The build is now complete — and still has never touched an antenna on transmit.** That last step waits for §4 |

Antenna work happens *between* stages whenever convenient (build
the 40 m dipole early — Stage 6 uses it for receiving), but the
transmit chain meets the antenna for the first time only after the
license exists. That sequencing is deliberate: by the day the
license arrives, there is nothing left to debug.

---

## 4. The legal frame — one honest section

- **Home-built vs bought makes no difference.** Pakistani law (PTA,
  Amateur Radio Services Regulations 2004 — see
  `FIRST_TX_ROUTES.md`) licenses the *act of transmitting* on
  amateur frequencies, not the purchase of equipment. A transmitter
  you soldered yourself needs the licence exactly as much as one
  from a shop — and is exactly as lawful once you hold it. Homebrew
  is a proud, explicitly contemplated part of the amateur service;
  it is not a loophole.
- **Until the licence:** build everything, power everything, test
  everything — **into a dummy load** (§3). Receive with any antenna,
  any time, no licence needed anywhere in this story. Do not connect
  the transmitter output to an antenna "just for a second, just for
  a test". The one-second test is the offence, and this project's
  entire record — the thing that makes strangers take it seriously —
  is that it has never once transmitted unlawfully. Keep it that
  way; the wait is months, the record is forever.
- **Licence-free bands are real but cannot do this job.** Pakistan's
  PTA SRD/IoT framework permits low-power licence-free operation
  around 433 MHz / 868 MHz / 2.4 GHz — those serve the project's
  *local* mesh layer (LoRa-class links), but they are line-of-sight
  frequencies: they will never bounce off the ionosphere, so they
  cannot substitute for HF in the mirror design. (And per
  `FIRST_TX_ROUTES.md`: CB 27 MHz and PMR446 have **no verified
  licence-exempt allocation in Pakistan — do not use them.**)
- **When the licence arrives** (PARS SWL → PTA test → licence; the
  ≈13–18 month path and ≈ PKR 5,000 total official cost are detailed
  in `FIRST_TX_ROUTES.md`): the first on-air transmission is the
  `TX_PACKAGE.md` sequence, under your own callsign, on a rig you
  can truthfully log as "homebrew, built and bench-proven [date]" —
  which is also, not incidentally, exactly the kind of station the
  amateur service exists to create.

---

## 5. Skills and tools

**You must own (buy once, cheap, in this order):**

| Item | Why | Est. PKR |
|---|---|---|
| Soldering iron, 30–40 W, fine tip (+ spare tips) | The whole project is solder joints; a temperature-controlled station is nicer but not required | 500–900 |
| Solder wire, 60/40, 0.8 mm, ~100 g | Joints; rosin-core only (never acid-core plumber's solder) | 300–600 |
| Digital multimeter | Already assumed in hand — volts, continuity, diode test for MOSFET/diode checks | — |
| Side cutters, needle-nose pliers, wire stripper, screwdrivers | Component leads, toroid winding, assembly | 800–1,500 (set) |
| Desolder braid or a cheap sucker | You *will* solder something in the wrong hole. Everyone does | 150–300 |

**Borrow, don't buy (one afternoon each is enough):**

- **An HF receiver or RTL-SDR** — for Stage-4 calibration and a
  qualitative harmonic listen (2nd harmonic of 7.074 = 14.148 MHz:
  with the LPF fitted it should be dramatically weaker than the
  fundamental at 1 m distance). A university electronics lab, PARS
  club station, or any licensed friend's shack covers this.
- **An oscilloscope** (university lab) — optional luxury; beautiful
  for seeing the square wave pre-filter and the near-sine after it.
- **A proper SWR/power meter** — later, at first-antenna time, from
  the same club/friend ecosystem. The RF probe carries you until
  then.

**Skills to grow (all learnable from the builds themselves):**
neat soldering (shiny, concave joints; 2 seconds of heat, not 10);
winding toroids without nicking enamel; reading a schematic as a
map rather than a picture; keeping a build log (Stage 8's notebook
page is a habit worth more than any instrument); and the discipline
of *one change at a time* when debugging. The Pixie (§2) exists in
this plan precisely because it teaches all of the above at the
lowest possible cost of failure.

---

## Sources (accessed 2026-10-20)

- Etherkit **JTEncode** library (Jason Milldrum NT7S) — modes,
  FT8/WSPR symbol generation, Si5351 pairing:
  github.com/etherkit/JTEncode · Arduino Library Registry entry.
- Etherkit **Si5351Arduino** library + App Notes (10 mW WSPR beacon):
  nt7s.com (Ripples in the Ether) · github.com/etherkit/Si5351Arduino.
- "Classie" BS170 WSPR transmitter (KC3XM; measurements by NT7S:
  ~1 W out / ~1.2 W DC in): nt7s.com, Jan 2015.
- *Careless WSPR* (Si5351 raw output ~12 mW, class-E experiments):
  hackaday.io/project/166875-careless-wspr.
- QRP Labs — **Si5351A Synth module** (US$7.50; 27 MHz reference note
  on exact WSPR tone spacing), **Low Pass Filter kit manual**
  (W3NQN/G-QRP values table, §1.5), **5 W HF PA kit** manual +
  simplified assembly (single IRF510, ~5 W @ 13.8 V, ~16 dB gain,
  ~200 mW drive; kit US$20, Jan 2017 newsletter): qrp-labs.com.
- Pixie lineage & kit survey (GM3OXX FOXX 1983 → RV3GM Micro-80
  1992 → WA6BOY Pixie 2 1995; kit power/harmonic specs from the
  standard kit documentation): amateurradio.com, "So you want to
  play with a Pixie?"; HamRadioShop.pl Pixie kit manual; CQ Magazine
  construction article, Feb 2018 (bg6tnb.github.io mirror).
- Prices: Daraz.pk ESP32 listings (Rs 1,378–1,785) · epro.pk Arduino
  Nano V3.0 (Rs 1,300) · AliExpress/Shenzhen Si5351 module listings
  (US$0.85–5.20) · Adafruit Si5351A breakout (US$7.95) — all
  **ESTIMATES** as flagged in §1.7, checked 2026-10-20.

*Companion documents: `TX_PACKAGE.md` (what gets transmitted, and
the report-back contract) · `FIRST_TX_ROUTES.md` (the licence path
and the PARS relay shortcut) · `OUTREACH_DRAFT.md` (the relay
request, awaiting the user's send decision).*
