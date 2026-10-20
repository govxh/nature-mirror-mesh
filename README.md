# Nature-Mirror Mesh

**A free, offline, end-to-end-encrypted chat backend that borrows nature's own infrastructure instead of renting mankind's.**

Full concept paper: `~/workspace/research_notes/physics-invention-offline-chat.md` (in the parent workspace) — *"Don't fight the horizon. Borrow a mirror that is already above it — or a particle that ignores it."*

## The idea

Every commercial chat system rents infrastructure: data centres, undersea cables, satellites, subscriptions. Nature-Mirror Mesh asks what physics already provides **for free, globally, and un-ownably**:

| Natural "mirror" | Role in the system |
|---|---|
| **Ionosphere** (HF radio) | The workhorse. A plasma mirror 100–1,000 km up that reflects HF signals around the planet (>4,000 km hops). Weak-signal digital modes (FT8/JS8-style, decoding near −24 dB) make text chat practical at modest power. |
| **Meteor trails** (VHF meteor-burst) | The gap-filler. Billions of meteors a day leave ionized trails that reflect VHF up to ~2,250 km for fractions of a second — perfect for queued burst messages when the ionosphere is unusable. |
| **The Moon** (EME / moonbounce) | The scheduled relay. When both continents can see the Moon, it is a free reflector nobody can switch off, tax, or jam. The app shows "Moon windows" the way calendars show prayer times. |
| **VLF/ELF earth–ionosphere waveguide** | The last-resort whisper: a few characters per minute, globally, through ocean and rock — a bell that says "come to a faster channel." |

An **AI propagation oracle** picks, moment by moment, which mirror is open (live ionosonde / GNSS-TEC data for HF, meteor-rate models, Moon position), and a **delay-tolerant glue layer** holds every message until a mirror opens. The user sees one chat app; underneath, physics is opportunistic.

## The glue layer — and what this repo proves

The transport is **Reticulum (RNS) + LXMF**: open-source, end-to-end encrypted (X25519 identity, ratcheting), store-and-forward messaging that treats every physical link — LoRa radio, packet radio, serial, TCP, HF gateway — as an interchangeable interface. That is exactly the property a multi-mirror backend needs: swap the mirror, keep the protocol.

**`lab/` contains a working proof of that layer, run 2026-10-20:**

- `lab/lxmf_two_node_test.py` — two independent Reticulum nodes (separate processes, separate config dirs) linked over a local TCP interface. Node B discovers Node A from its announce, and delivers an LXMF message whose unique runtime token Node A prints **decrypted**. Exit code 0 only on an exact token match.
- **Result: ✅ PASS, twice** (tokens `NMM-TEST-20261020-065214` and `NMM-TEST-20261020-065226`). Full log: `lab/results/lxmf_test.log`. Honest details — including a sandbox UDP block, a Meshtastic "hardware required" verdict, and an FT8 decode that did **not** verify — are in `lab/results/RESULTS.md`.

No radio hardware exists on the machine that ran the lab, and **no radio transmission was made**. The local link stands in for a future radio interface; proving the mirrors over the air is the next phase (roadmap in the concept paper: RTL-SDR reception tests → licensed JS8Call loop → meteor-scatter reception → EME reception).

## Layout

```
nature-mirror-mesh/
├── README.md                  ← this file
└── lab/
    ├── lxmf_two_node_test.py  ← Reticulum + LXMF two-node delivery test (PASS)
    ├── ft8_codec_test.py      ← FT8 codec round-trip attempt (decode not verified — see RESULTS.md)
    ├── venv/                  ← local Python venv (git-ignored; recreate: python3 -m venv venv && venv/bin/pip install rns lxmf meshtastic)
    └── results/
        ├── RESULTS.md         ← the honest lab record
        ├── lxmf_test.log      ← full passing-run output
        └── ft8_codec_test.log ← FT8 attempt output
```

## Run the proof yourself

```bash
cd lab
python3 -m venv venv
venv/bin/pip install rns lxmf
venv/bin/python lxmf_two_node_test.py   # exit 0 + "RESULT: PASS" = encrypted delivery verified
```

## Status & honesty labels

- **Proven:** the encrypted store-and-forward transport layer (Reticulum/LXMF), locally.
- **Evidence-based, not yet built here:** the three mirrors (HF/meteor/EME) — each is demonstrated physics in the literature (see the concept paper and the companion research in `~/workspace/research_notes/`), but this project has not yet transmitted or received over any of them.
- **Speculative frontier:** the concept paper's "Earth-Chord" neutrino link — a research bet, not a product claim.
