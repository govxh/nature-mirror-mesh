# Independent re-decode of the kiwisdr-reception artifact WAV

Artifact: `kiwisdr_recording.wav` from run 39389957321 (sha256 of zip verified; see AUDIT_kiwisdr.md).
Receiver (per kiwisdr_ci.log): emeraldsdr.ddns.net:8073, Carlow, Ireland - 14074 kHz USB, passband 200-3000 Hz.
Decoder: lab/ft8_lib/decode_ft8 via lab/ft8_slot_decode.py (UTC-slot-aligned, each slot decoded exactly once).

Two alignments are reported. PRIMARY uses the log's banner start (2026-10-20T07:57:25Z, first slot boundary at file offset 5.00 s) exactly as the audit task specifies. SENSITIVITY uses start+2.0 s (boundary at 3.00 s), justified by two independent measurements of the true slot-grid phase in the audio itself (envelope best-fit 2.60 s; DT-cluster 3.44 s): the banner timestamp precedes the first audio sample by ~1.6-2.4 s (kiwirecorder connect latency). The table below is the SENSITIVITY decode (DTs cluster at 0.0..+1.2 s, i.e. sane), with each message flagged if its text also appears in the CI log's 58.

| # | Slot (UTC) | Approx UTC (slot+DT) | DT (s) | Freq (Hz) | Message | In log's 58? |
|---|------------|----------------------|--------|-----------|---------|:---:|
| 1 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 2891 | EA4CPM <...> -09 | yes |
| 2 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 2722 | PD3CFG F5OYA/P JN13 | yes |
| 3 | 2026-10-20T07:57:30Z | 07:57:30.4 | +0.40 | 2469 | M9RPO OE3EHS JN87 | yes |
| 4 | 2026-10-20T07:57:30Z | 07:57:30.4 | +0.40 | 2191 | IU1WVQ OH3BYZ RR73 | yes |
| 5 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 2034 | V31DL DL5ARG JO60 | yes |
| 6 | 2026-10-20T07:57:30Z | 07:57:30.4 | +0.40 | 1800 | TF4CU EA4ITM IN80 | yes |
| 7 | 2026-10-20T07:57:30Z | 07:57:31.4 | +1.44 | 1750 | BD2BN F4DIA R-15 | yes |
| 8 | 2026-10-20T07:57:30Z | 07:57:30.5 | +0.48 | 1494 | CQ S55X JN76 | yes |
| 9 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 1456 | CQ HA1ZW JN86 | yes |
| 10 | 2026-10-20T07:57:30Z | 07:57:30.5 | +0.48 | 1306 | CQ VK SN5N KO11 | yes |
| 11 | 2026-10-20T07:57:30Z | 07:57:31.5 | +1.52 | 1197 | ON3HVP LB7YK +20 | yes |
| 12 | 2026-10-20T07:57:30Z | 07:57:30.6 | +0.56 | 1116 | OE8PPL SM7DUZ R+07 | yes |
| 13 | 2026-10-20T07:57:30Z | 07:57:30.5 | +0.48 | 1066 | CQ P4/WE9V | yes |
| 14 | 2026-10-20T07:57:30Z | 07:57:30.5 | +0.48 | 1006 | ZL1MED OZ4ACK JO65 | yes |
| 15 | 2026-10-20T07:57:30Z | 07:57:30.4 | +0.40 | 947 | BI4JJO DH1AKG JO60 | yes |
| 16 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 784 | CQ CT7BRV IM58 | yes |
| 17 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 725 | SV5AZK S51NO -03 | yes |
| 18 | 2026-10-20T07:57:30Z | 07:57:30.3 | +0.32 | 619 | F4FDR DG6TOM JN58 | yes |
| 19 | 2026-10-20T07:57:30Z | 07:57:30.6 | +0.56 | 291 | CQ IW2NEF JN46 | yes |
| 20 | 2026-10-20T07:57:45Z | 07:57:45.3 | +0.32 | 2569 | RW9UKK DK0ULR JN58 | yes |
| 21 | 2026-10-20T07:57:45Z | 07:57:45.3 | +0.32 | 2397 | DD5TL EA5DQW IM99 | yes |
| 22 | 2026-10-20T07:57:45Z | 07:57:45.3 | +0.32 | 1944 | E79KO UA3PAB KO84 | yes |
| 23 | 2026-10-20T07:57:45Z | 07:57:45.4 | +0.40 | 1881 | CQ EB3DIY JN01 | yes |
| 24 | 2026-10-20T07:57:45Z | 07:57:45.2 | +0.16 | 1497 | SM7DUZ OE8PPL RR73 | yes |
| 25 | 2026-10-20T07:57:45Z | 07:57:45.2 | +0.16 | 1150 | BG2GFW LY3PW RRR | yes |
| 26 | 2026-10-20T07:57:45Z | 07:57:45.3 | +0.32 | 1069 | S55X IN3ADG -23 | yes |
| 27 | 2026-10-20T07:57:45Z | 07:57:45.4 | +0.40 | 988 | ON7YC PY7ZC RR73 | yes |
| 28 | 2026-10-20T07:57:45Z | 07:57:45.6 | +0.56 | 881 | IU4FLR V31DL 73 | yes |
| 29 | 2026-10-20T07:57:45Z | 07:57:45.7 | +0.72 | 788 | CT7BRV EA2BHE IN83 | yes |
| 30 | 2026-10-20T07:57:45Z | 07:57:45.3 | +0.32 | 588 | H49A CT4NH IM58 | yes |
| 31 | 2026-10-20T07:57:45Z | 07:57:45.4 | +0.40 | 384 | RN3YN IK4LZH JN54 | yes |
| 32 | 2026-10-20T07:58:00Z | 07:58:00.2 | +0.24 | 2891 | EA4CPM <...> -09 | yes |
| 33 | 2026-10-20T07:58:00Z | 07:58:00.3 | +0.32 | 2722 | BG3GP OH2XO -10 | yes |
| 34 | 2026-10-20T07:58:00Z | 07:58:00.4 | +0.40 | 2469 | M9RPO OE3EHS JN87 | yes |
| 35 | 2026-10-20T07:58:00Z | 07:58:00.4 | +0.40 | 2009 | PY7ZC IK1QLD JN34 | yes |
| 36 | 2026-10-20T07:58:00Z | 07:58:00.3 | +0.32 | 1800 | TF4CU EA4ITM IN80 | yes |
| 37 | 2026-10-20T07:58:00Z | 07:58:02.0 | +2.00 | 1750 | BD2BN F4DIA 73 | yes |
| 38 | 2026-10-20T07:58:00Z | 07:58:00.5 | +0.48 | 1497 | CQ S55X JN76 | yes |
| 39 | 2026-10-20T07:58:00Z | 07:58:00.0 | +0.00 | 1422 | CQ SP3DOF JO72 | yes |
| 40 | 2026-10-20T07:58:00Z | 07:58:00.4 | +0.40 | 1247 | CQ OE1EZA JN88 | yes |
| 41 | 2026-10-20T07:58:00Z | 07:58:01.2 | +1.20 | 1197 | ON3HVP LB7YK RR73 | yes |
| 42 | 2026-10-20T07:58:00Z | 07:58:00.5 | +0.48 | 1066 | CQ P4/WE9V | yes |
| 43 | 2026-10-20T07:58:00Z | 07:58:00.6 | +0.56 | 1006 | ZL1MED OZ4ACK JO65 | yes |
| 44 | 2026-10-20T07:58:00Z | 07:58:00.4 | +0.40 | 947 | BI4JJO DH1AKG JO60 | yes |
| 45 | 2026-10-20T07:58:00Z | 07:58:00.3 | +0.32 | 788 | CQ CT7BRV IM58 | yes |
| 46 | 2026-10-20T07:58:00Z | 07:58:00.4 | +0.40 | 703 | PY1EW SM6UQL -01 | yes |
| 47 | 2026-10-20T07:58:00Z | 07:58:00.6 | +0.56 | 291 | CQ IW2NEF JN46 | yes |
| 48 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 2781 | S51NO DL1BBO JO43 | yes |
| 49 | 2026-10-20T07:58:15Z | 07:58:15.5 | +0.48 | 2712 | C5R JH1FYC PM95 | yes |
| 50 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 2569 | RW9UKK DK0ULR JN58 | yes |
| 51 | 2026-10-20T07:58:15Z | 07:58:15.5 | +0.48 | 2459 | H49A OH1JO R-13 | yes |
| 52 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 2397 | DD5TL EA5DQW R-13 | yes |
| 53 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 1944 | E79KO UA3PAB KO84 | yes |
| 54 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 1897 | H49A CT4NH IM58 | yes |
| 55 | 2026-10-20T07:58:15Z | 07:58:15.4 | +0.40 | 1722 | BG2KSI IV3UWA JN66 | yes |
| 56 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 1622 | CQ F4FDR JN04 | yes |
| 57 | 2026-10-20T07:58:15Z | 07:58:15.7 | +0.72 | 1550 | OK2AB EA2BHE IN83 | yes |
| 58 | 2026-10-20T07:58:15Z | 07:58:14.8 | -0.16 | 1500 | DB2QM F4NHL RR73 | yes |
| 59 | 2026-10-20T07:58:15Z | 07:58:15.1 | +0.08 | 1150 | CQ LY3PW KO05 | yes |
| 60 | 2026-10-20T07:58:15Z | 07:58:15.3 | +0.32 | 1069 | S55X IN3ADG -23 | yes |
| 61 | 2026-10-20T07:58:15Z | 07:58:15.1 | +0.08 | 878 | CQ OM7AMA JN98 | yes |
| 62 | 2026-10-20T07:58:15Z | 07:58:14.9 | -0.08 | 528 | E79KO RZ7KR -09 | yes |
| 63 | 2026-10-20T07:58:15Z | 07:58:15.4 | +0.40 | 384 | CQ IK4LZH JN54 | yes |
| 64 | 2026-10-20T07:58:30Z | 07:58:30.2 | +0.24 | 2891 | <...> DA125RH RR73 | yes |
| 65 | 2026-10-20T07:58:30Z | 07:58:30.3 | +0.32 | 2722 | BG3GP OH2XO RR73 | yes |
| 66 | 2026-10-20T07:58:30Z | 07:58:30.5 | +0.48 | 2469 | M9RPO OE3EHS JN87 | yes |
| 67 | 2026-10-20T07:58:30Z | 07:58:30.4 | +0.40 | 2009 | PY7ZC IK1QLD R-14 | yes |
| 68 | 2026-10-20T07:58:30Z | 07:58:31.2 | +1.20 | 1834 | RV9CD SP2KW JO92 | yes |
| 69 | 2026-10-20T07:58:30Z | 07:58:30.5 | +0.48 | 1497 | CQ S55X JN76 | yes |
| 70 | 2026-10-20T07:58:30Z | 07:58:30.0 | +0.00 | 1422 | CQ SP3DOF JO72 | yes |
| 71 | 2026-10-20T07:58:30Z | 07:58:30.5 | +0.48 | 1334 | LZ1MIT DG1RMY JO62 | yes |
| 72 | 2026-10-20T07:58:30Z | 07:58:31.2 | +1.20 | 1197 | ON3HVP LB7YK 73 | yes |
| 73 | 2026-10-20T07:58:30Z | 07:58:30.3 | +0.32 | 1134 | CQ IU0SIJ/QRP | yes |
| 74 | 2026-10-20T07:58:30Z | 07:58:30.5 | +0.48 | 1006 | ZL1MED OZ4ACK JO65 | yes |
| 75 | 2026-10-20T07:58:30Z | 07:58:30.4 | +0.40 | 947 | BI4JJO DH1AKG JO60 | yes |
| 76 | 2026-10-20T07:58:30Z | 07:58:30.3 | +0.32 | 788 | JA1LLG CT7BRV -15 | yes |
| 77 | 2026-10-20T07:58:30Z | 07:58:30.4 | +0.40 | 703 | PY1EW SM6UQL -01 | yes |
| 78 | 2026-10-20T07:58:30Z | 07:58:30.6 | +0.56 | 291 | CQ IW2NEF JN46 | yes |
| 79 | 2026-10-20T07:58:45Z | 07:58:45.5 | +0.48 | 2712 | C5R JH1FYC R-07 | NEW |
| 80 | 2026-10-20T07:58:45Z | 07:58:45.2 | +0.16 | 2603 | OK2AB IU8RFW JN70 | NEW |
| 81 | 2026-10-20T07:58:45Z | 07:58:45.5 | +0.48 | 2462 | H49A OH1JO R-13 | yes |
| 82 | 2026-10-20T07:58:45Z | 07:58:45.3 | +0.32 | 1944 | E79KO UA3PAB KO84 | yes |
| 83 | 2026-10-20T07:58:45Z | 07:58:45.4 | +0.40 | 1800 | S55X EA4ITM IN80 | NEW |
| 84 | 2026-10-20T07:58:45Z | 07:58:45.3 | +0.32 | 1681 | H49A CT4NH IM58 | yes |
| 85 | 2026-10-20T07:58:45Z | 07:58:45.3 | +0.32 | 1622 | MM7CEH F4FDR -03 | NEW |
| 86 | 2026-10-20T07:58:45Z | 07:58:45.7 | +0.72 | 1550 | OK2AB EA2BHE IN83 | yes |
| 87 | 2026-10-20T07:58:45Z | 07:58:44.8 | -0.16 | 1500 | CQ F4NHL IN94 | NEW |
| 88 | 2026-10-20T07:58:45Z | 07:58:45.2 | +0.16 | 1150 | CQ LY3PW KO05 | yes |
| 89 | 2026-10-20T07:58:45Z | 07:58:45.3 | +0.32 | 1069 | CQ IN3ADG JN56 | NEW |
| 90 | 2026-10-20T07:58:45Z | 07:58:45.3 | +0.32 | 988 | IK1QLD PY7ZC RR73 | NEW |
| 91 | 2026-10-20T07:58:45Z | 07:58:45.1 | +0.08 | 878 | CQ OM7AMA JN98 | yes |
| 92 | 2026-10-20T07:58:45Z | 07:58:45.4 | +0.40 | 384 | CQ IK4LZH JN54 | yes |

Totals: sensitivity decode = 92 (slot,text) decodes, 65 unique texts; primary (banner) decode = 69 (slot,text) decodes, 49 unique texts; CI log = 58 unique texts / 180 events (stride method).

Texts in the log's 58 but recovered by NEITHER aligned decode: none

Note: approx UTC = slot start + decode_ft8 DT; DT carries the decoder's own convention (a gen_ft8 file placed exactly at a slot start reads DT +1.36 in this build), so treat absolute times as +/- ~1.5 s. Slot attribution is exact by construction.
