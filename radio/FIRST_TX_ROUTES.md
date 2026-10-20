# FIRST_TX_ROUTES.md — Every legitimate $0 route to the first real on-air test

Project: **Nature-Mirror Mesh** — offline, encrypted chat proven in simulation
(Reticulum/LXMF), with its message *content* proven across a simulated HF
channel as a plaintext FT8 beacon (`lab/tx_chain_test.py`, PASS at −5/−10/−15 dB).
Research date: **2026-10-20**. Requester profile: Pakistani citizen, 19,
university student, $0 budget, **no radio hardware, no amateur license (yet)**.

> Legal frame applied to every route below: transmitting on amateur bands
> requires a license; encryption is prohibited on amateur bands, so any
> ham-band test payload must be **plaintext** (our FT8 beacon format already
> is — callsign-shaped plain text, publicly documented mapping). Nothing in
> this document suggests unlicensed transmission on ham bands or defeating
> type-approval rules.

---

## 1. His own license (Pakistan) — the complete, sourced process

**Issuing authority:** Pakistan Telecommunication Authority (PTA),
Radio-Based Services (RBS) section, PTA Headquarters, F-5/1, Islamabad.
Application goes to the **Director (Radio Based Services), PTA HQ**
(per PTA's own application form).

**Governing law:** The Amateur Radio Services Regulations, 2004
(S.R.O. 797(I)/2004), plus PTA's SOP on the award of the Amateur Radio
Wireless License (referenced on PTA's application form; the SOP summary is
mirrored by the Pakistan hams community wiki).

**Eligibility (PTA application form + SOP summary):**
- Pakistani citizen; **minimum age 16** (the 2004 Regulations' text says 18;
  the operational SOP/form says 16 — the SOP is what PTA actually applies;
  the Oct 2026 *draft* rules propose 18 again, see §1.4). At 19, Imran
  qualifies under every version.
- Able to communicate in English.
- **Short Wave Listener (SWL) member of PARS (Pakistan Amateur Radio
  Society) or a PTA-acceptable radio club for at least 1 year** (age ≥18);
  2 years if aged 16–<18; able to present a significant number of QSL
  acknowledgement cards. *(The 2004 Regulations §3(e) literally says "SWL
  for at least three years"; the PTA SOP and application form say 1 year
  for 18+. Follow the SOP/form — and confirm with PTA/PARS when joining.)*
- Pass the **prescribed written test and interview**.
- The 2004 Regulations also allow exemption from the exam for holders of a
  telecommunications degree/diploma or long professional wireless
  experience (§3) — not applicable to a BS English student.

**Examination:** Conducted by **PTA (HQ and Regional Offices), in
collaboration with PARS** (Regulations §3(d), §5). Fee in the 2004
Regulations: **Rs 100** by pay order/bank draft (2004 schedule — may have
been revised; see §1.4). The test is per the syllabus in **Annex VIII** of
the Regulations ("technical and procedural test"). The full Annex VIII
text is not reproduced in the public mirrors found; regional
operator-certificate syllabi of the same family cover (a) radio theory and
practice and (b) national + ITU radio regulations — **treat the exact
subject list as to-be-confirmed with PTA/PARS** before the test; PARS
helps applicants prepare (Dawn, 2026 feature).

**Documents (PTA form):** attested CNIC copy; two attested passport
photos; list of equipment incl. antenna layout sketch; proof of the SWL
membership period; sketch of the station's exact geographical location
(for PTA inspector verification); any supporting certificates.

**Security clearance:** Where credentials raise doubts, PTA refers the
applicant to local police for verification of antecedents; if no police
response is received, the license issues **within 8 weeks** (Regulations
§4(3)). Dawn's 2026 feature reports the process involves law-enforcement
clearance and **can take longer than the stipulated ~12 weeks**, with
rejections not always clearly explained. The Oct 2026 draft rules would
make a police clearance certificate mandatory for everyone.

**Fees (PKR) — three schedules exist; read carefully:**
| Item | Amount | Source / status |
|---|---|---|
| Exam fee | **Rs 100** | Amateur Radio Services Regulations 2004, §5 (gazetted; possibly superseded — verify) |
| License fee (2004 schedule) | Rs 50/year; renewal up to 5 years | Regulations 2004, §§6–7 (superseded in practice, below) |
| License fee (current practice, from Jul 2025) | **Rs 2,000 per 5-year term** | PTA revised flat-rate RBS schedule as published by PhoneWorld (2025); confirmed independently by Dawn's 2026 PARS feature ("The license fee is Rs 2,000 and has to be renewed every five years") |
| PARS SWL membership (student) | **PKR 3,000 for 3 years** | PARS official membership form (2026) — students; non-students PKR 4,500/3 years; licensed amateurs PKR 2,000/year |

One secondary source (ICQ Podcast, Aug 2025) reported the amateur fee
rising "from Rs 450 to Rs 5,000"; this conflicts with the published
flat-rate schedule and Dawn. **Status: the Rs 2,000 / 5-year figure is the
best-corroborated; the exact total payable at application time is
UNCONFIRMED — verify with PTA RBS before paying anything.**

**Realistic timeline for Imran (shortest legitimate path):**
1. **Now (week 1):** Join PARS as an SWL (student rate). Start listening
   (any receiver / free WebSDR) and collecting QSL cards. This starts the
   mandatory 1-year SWL clock — it is the long pole; nothing lawful
   shortens it (the Regulations let PTA license "anyone otherwise found
   suitable," but that discretion cannot be planned on).
2. **Month 12:** Apply to PTA (form + documents above).
3. **Months 12–15+:** Written test + interview (PTA/PARS schedule),
   police verification; license issuance.
**Total: ≈ 13–18 months, total official cost on the order of Rs 5,000**
(membership 3,000 + exam ~100 + license 2,000, per the schedules above)
plus stamp paper/photos. The license itself is initially issued for one
year, renewable for five-year terms (ICQ/Dawn reporting).

**Student/youth concessions found:** PARS student SWL rate
(PKR 3,000/3 yrs vs 4,500). The **draft** RBS Regulations 2026 propose a
*free junior license* — but for ages 14–<18, so it would not apply to
Imran (19), and it is not yet law (§1.4).

### 1.4 Regulatory change in flight (Oct 2026)
PTA has proposed **Radio Based Services (RBS) Licensing Regulations,
2026** (reported by Business Recorder, 2026-10-19; TechJuice; TechX):
10-year license terms, online processing, decision within 15 working days
of a complete application; amateur license **Rs 2,000 for 10 years**;
junior license (14–<18, with sponsorship/parental consent) **free**;
minimum age 18 for the full license; valid PARS membership and police
clearance mandatory. **Status: DRAFT/proposed — not confirmed in force
as of 2026-10-20.** If enacted as reported, it does not remove the SWL
apprenticeship question — whether the 1-year SWL prerequisite survives is
not stated in the reports; confirm with PTA/PARS.

Sources (§1): Amateur Radio Services Regulations 2004 (gazette text,
joshandmakinternational.com mirror); PTA amateur application form
(pta.gov.pk, form_citizens_pak_071118.pdf); PTA SOP summary
(github-wiki-see.page/m/amingilani/pakistan-hams — community mirror of
PTA SOPs); PARS membership form (pars.pk, 2026); Dawn feature
"dawn.com/news/2025392" (2026); PhoneWorld RBS charges list (2025);
Business Recorder 2026-10-19 & TechJuice (draft 2026 rules).

---

## 2. Licensed-operator relay (a control operator transmits our beacon)

**Model:** A licensed Pakistani amateur — most plausibly the **PARS club
station** or an individual PARS member — transmits the one-time plaintext
test beacon **as his own station operation, under his own callsign and
control**, and logs it. Imran never touches the transmitter. This matches
how the Regulations frame things: the station "shall not be operated by
any other person(s) except the person duly Licensed" (§16(3)), content is
restricted to plain language about technology/propagation (§17(2)) — the
beacon is exactly a technical/propagation test — and messages must not be
commercial or for pecuniary reward (§17(3)(c)); this is a non-commercial
student research experiment, and the final decision rests with the
control operator.

**Named organizations + public contact channels (only what sources show):**
- **Pakistan Amateur Radio Society (PARS)** — IARU member society for
  Pakistan. Club station callsign **AP2ARS** (historically at G-10/4,
  Islamabad, per PARS's own compiled history on qsl.net). Public
  channels: **www.pakhams.com**, **pars.pk**, and
  **facebook.com/pakhams/** (both printed on PARS's official membership
  form). Postal (QSL bureau, from the PARS page on qsl.net): Post Box
  1450, Islamabad 44000 — old listing, verify before use. PARS runs
  licensing-prep and student outreach (2026: antenna workshop at NUST,
  per Dawn) — a one-time student experiment beacon is squarely in its
  stated education mission (pars.pk: "Education & Training … workshops,
  licensing programs").
- **University club stations:** The 2004 Regulations (§3(2)) allow bona
  fide clubs/schools/colleges/universities to hold a station license with
  at least one licensed staff member supervising. **No specific Pakistani
  university amateur club station (callsign/contact) could be verified
  from public sources in this research** — the realistic route to one is
  *through PARS*, which works with universities. Do not invent one.
- **Individual operators:** Pakistan has ~160 active licensed operators
  (Dawn, 2026). Individual callsigns/contacts are listed in public
  callbooks (e.g., QRZ), but this document deliberately does **not**
  compile private individuals' emails; outreach should go through PARS
  as the front door. (Older PARS officer emails circulating on qsl.net
  are stale — the long-serving president AP2NK became a silent key in
  2025, per Dawn — do not use them.)

**Cost/time/legitimacy:** $0; days-to-weeks once PARS replies (entirely
at their discretion); fully lawful *if* the operator transmits and logs
it as his own operation. **This is the only route that can lawfully put
our beacon on air without Imran holding a license.**

Prepared outreach text: `radio/OUTREACH_DRAFT.md` (not sent).

---

## 3. Internet-controllable transmitters — verified eligibility

Every self-serve remote-transmit service found **requires the user to
hold his own amateur license**. None admits an unlicensed user "under a
control operator" through its normal signup:

| Service | TX eligibility (from the service's own pages/materials) | Verdict for Imran |
|---|---|---|
| **RemoteHamRadio (RHR)** | Signup requires a **valid FCC amateur callsign, General class or above**; non-US operators need a license with a CEPT agreement with the US; send a copy of your license. Paid (first 30 min free trial for licensees). Youth Program free access still requires **age ≤25 + General class or higher + ARRL membership** (per program criteria reported by N0SSC). A secondary blog claimed youth access with "no license required" — this contradicts RHR's own stated requirement and program criteria; **not relied on**. | ❌ Needs his own license |
| **RemoteHams.com** (RCForb) | Free; **listening needs no license**, but **transmit requires uploading a copy of your amateur license**, and each station owner approves TX privileges individually. | ❌ TX needs his own license (RX is open — useful for monitoring our beacon!) |
| **HamSphere** | A *simulated* radio network — no real RF is transmitted at all; its Remote Station terms require licensed operators anyway. | ❌ Not real RF; also licensed-only |
| **Amateur satellite digipeaters** (e.g., ISS packet digipeater, amateur satellites) | These are amateur-satellite-service uplinks: transmitting to them requires an amateur license under the same rules as any amateur band. Ground-station networks (SatNOGS etc.) are **receive-only** for the public. | ❌ Needs license |

**Honest summary:** there is no legitimate "log in and transmit"
service open to an unlicensed person. The control-operator concept exists
only in person (Route 2), not as an internet service.

Sources (§3): remotehamradio.com signup/newsletter (license requirement);
handiham.org RemoteHams user manual + slidetodoc RemoteHams briefing
(license upload for TX; RX free); hs50.hamsphere.com HRS terms;
n0ssc.com (RHR Youth Program criteria).

---

## 4. License-free transmission options in Pakistan (when hardware exists)

Under PTA's **Regulatory Framework for SRD & Terrestrial IoT**
(license-exempt category; Version 1.4 reported issued 2025-12-18 by CSA
Group's regulatory update), devices in the framework's shared bands are
**license-exempt only if**: within the Annex power/duty-cycle limits,
**PTA type-approved** (Telecom Act §29 — type approval is mandatory even
for license-exempt devices), operated on a non-interference,
non-protection basis, and stopped immediately if they interfere.

| Option | Band / limits (as published) | Cheapest hardware class | Fit for NMM |
|---|---|---|---|
| SRD 868 MHz | 868–868.6 MHz, 25 mW ERP, duty-cycle limits (compliance tables for PTA framework) | LoRa dev boards (ESP32+SX1276-class, e.g. Heltec WiFi LoRa) — the Meshtastic-class node | Local mesh only (km-scale). Cannot do the HF skywave test. Meshtastic has **no Pakistan region preset**; device choice/band must be matched to PTA's Annex and type approval — verify before purchase |
| SRD 433 MHz | 433.05–434.79 MHz ISM/SRD region used internationally; confirm against current PTA Annex before use | Same LoRa board class (433 MHz variant) | Local mesh only; same type-approval caveat |
| 2.4 GHz | 2400–2483.5 MHz, 100 mW EIRP (WiFi/Bluetooth) | Any ESP32-class board / phone itself | Metres-to-100 m; link layer only |
| **CB (27 MHz)** | **No Pakistani license-exempt CB allocation was found in PTA sources.** CB is license-free in the US/EU — that does **not** transfer to Pakistan. | — | ⚠️ **Do not assume legal. Do not use without written PTA confirmation.** |
| **PMR446** | A European allocation; **not a Pakistani license-exempt service** in any PTA source found. | — | ⚠️ **Not usable as "license-free" in Pakistan.** |

All of §4 needs hardware (>$0 today) and none of it reaches the
ionosphere — it is recorded for the day a few thousand rupees exist, for
the *local* layer of Nature-Mirror Mesh, not for the first HF test.

Sources (§4): PTA SRD/IoT Regulatory Framework (pta.gov.pk PDF, 2022
edition text via search extract); CSA Group regulatory update (PTA
framework v1.4, 2025-12-18); Eleos Compliance Pakistan type-approval
frequency table; PTA Type Approval FAQ (pta.gov.pk, 2025-07-23).

---

## 5. Routes ranked (cost · time · legitimacy)

| # | Route | Cost | Time to first TX | Legitimacy | Status |
|---|---|---|---|---|---|
| 1 | **PARS / club-station control-operator relay** (§2) | $0 | Days–weeks, at PARS's discretion | Lawful: licensed operator transmits & logs his own test | **Possible this week ONLY if PARS/a member agrees.** Outreach drafted, not sent |
| 2 | **His own PTA license** (§1) | ≈ Rs 5,000 official total (schedules cited; verify) | **≥ ~13 months** (1-yr SWL prerequisite + test/interview + clearance) | Full | Start the SWL clock NOW — every week of delay moves the license a week |
| 3 | Remote TX services (RHR / RemoteHams) (§3) | $0–paid | — | Lawful but **license-gated** | Blocked until Route 2 completes |
| 4 | Satellite digipeaters (§3) | $0 | — | License-gated uplinks | Blocked until Route 2 |
| 5 | License-free SRD/LoRa (§4) | Needs hardware (>$0) | When hardware exists | Lawful with type-approved devices within limits | Local-layer only; **cannot** substitute for the HF test |

## Bottom line

- **Possible NOW ($0, lawful):** exactly one thing — *ask* a licensed
  Pakistani operator (via PARS) to transmit our plaintext beacon as
  control operator. If yes, first real TX can happen within days, in
  about 5 minutes of airtime prep (`radio/TX_PACKAGE.md`). If no, no
  lawful self-serve alternative exists this week: **no internet
  transmitter, satellite service, or license-free band lets an
  unlicensed person put this signal on HF — anyone claiming otherwise is
  describing piracy.**
- **Needs the license:** everything self-operated on amateur bands.
  The path is cheap (≈ Rs 5,000 in official fees/membership per current
  schedules) but has a hard 1-year SWL apprenticeship — join PARS as an
  SWL immediately to start the clock.
- **Needs hardware:** the license-free local layer (LoRa/SRD) — a
  future, separate purchase; irrelevant to the first HF transmission.
- **Meanwhile, free and lawful today:** receive-only monitoring
  (WebSDR/KiwiSDR, RemoteHams RX) to verify any relayed beacon and watch
  PSK Reporter — the same receive half this project already proved with
  real off-air KiwiSDR audio.

*All facts above are from the cited sources as of 2026-10-20; items
marked UNCONFIRMED or DRAFT must be re-verified with PTA/PARS before
money or airtime depends on them.*
