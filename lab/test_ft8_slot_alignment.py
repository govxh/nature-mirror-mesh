#!/usr/bin/env python3
"""
Nature-Mirror Mesh -- DETERMINISTIC synthetic test for ft8_slot_decode.py
(audit fix, 2026-10-20). No randomness in outcomes: fixed noise seed,
fixed messages, fixed geometry. Exit 0 only if EVERY assertion passes.

GEOMETRY
--------
Synthetic recording start: 2026-10-20T08:00:07.300Z.
start_epoch mod 15 = 7.30 s, i.e. the recording begins 7.30 s into a UTC
FT8 slot, so offset_to_first_slot must be 7.70 s and the UTC-aligned
slots inside the file are:

    file [ 7.7, 22.7)  -> slot 2026-10-20T08:00:15Z   message A
    file [22.7, 37.7)  -> slot 2026-10-20T08:00:30Z   message B
    file [37.7, 52.7)  -> slot 2026-10-20T08:00:45Z   message C
    file [52.7, 67.7)  -> slot 2026-10-20T08:01:00Z   noise only

A, B, C are gen_ft8 waveforms (each verified beforehand to round-trip
exactly through decode_ft8) mixed at their slot starts at distinct audio
frequencies (800 / 1300 / 1900 Hz) over a fixed-seed noise bed.

WHY C IS THE SHARP CASE: under the OLD naive slicing (15 s windows from
file offset 0), C's transmission [37.7, ~50.3) is split by the naive
window edge at 45.0 s: window [30,45) holds only its first ~7.3 s and
window [45,60) only its tail -- neither holds the whole transmission.
A slot-aligned decoder must recover C whole, exactly once, attributed
to 08:00:45Z. (The naive behaviour is printed for information only;
assertions bind the slot decoder, not the straw man.)

ASSERTIONS
----------
1. offset_to_first_slot in the decoder's headers == 7.70 s.
2. A recovered exactly once, slot 2026-10-20T08:00:15Z.
3. B recovered exactly once, slot 2026-10-20T08:00:30Z.
4. C recovered exactly once, slot 2026-10-20T08:00:45Z.
5. Noise slot 2026-10-20T08:01:00Z yields zero messages.
6. Total unique (slot, text) messages == 3.
"""

import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ft8_slot_decode import slot_decode  # noqa: E402

GEN = os.path.join(HERE, "ft8_lib", "gen_ft8")
DEC = os.path.join(HERE, "ft8_lib", "decode_ft8")
RATE = 12000
START_UTC = "2026-10-20T08:00:07.300Z"
MSGS = [("CQ T1ST JN46", 800, 7.7, "2026-10-20T08:00:15Z", "A"),
        ("CQ T2ST JO62", 1300, 22.7, "2026-10-20T08:00:30Z", "B"),
        ("CQ T3ST JN58", 1900, 37.7, "2026-10-20T08:00:45Z", "C")]
NOISE_SLOT = "2026-10-20T08:01:00Z"
DUR_S = 68.0


def gen_wav(msg, freq, path):
    subprocess.run([GEN, msg, path, str(freq)], check=True,
                   capture_output=True)
    w = wave.open(path, "rb")
    x = np.frombuffer(w.readframes(w.getnframes()),
                      dtype=np.int16).astype(np.float64)
    w.close()
    return x


def main():
    tmp = tempfile.mkdtemp(prefix="slot_test_")
    rng = np.random.default_rng(1234)
    mix = rng.normal(0, 500, int(DUR_S * RATE))
    for msg, freq, off, _slot, _name in MSGS:
        x = gen_wav(msg, freq, os.path.join(tmp, "gen.wav"))
        # normalize each gen waveform to a robust level (RMS 4500)
        x = x * (4500.0 / np.sqrt(np.mean(x ** 2)))
        s0 = int(round(off * RATE))
        mix[s0:s0 + len(x)] += x
    mix = np.clip(mix, -32767, 32767).astype(np.int16)
    rec = os.path.join(tmp, "synthetic_recording.wav")
    w = wave.open(rec, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(mix.tobytes())
    w.close()
    print("Synthetic recording: %s (%.1f s, start %s, epoch mod 15 = "
          "7.30 s)" % (rec, DUR_S, START_UTC))

    headers, messages = slot_decode(rec, START_UTC, DEC)
    for h in headers:
        print("# " + h)
    for m in messages:
        print("DECODED slot=%s dt=%+.2f freq=%d text=%s"
              % (m["slot_utc"], m["dt"], m["freq_hz"], m["text"]))

    fails = []

    def check(cond, label):
        print(("PASS  " if cond else "FAIL  ") + label)
        if not cond:
            fails.append(label)

    check(any("Offset to first UTC slot boundary: 7.70 s" in h
              for h in headers),
          "offset_to_first_slot == 7.70 s")
    for _msg, _f, _o, slot, name in MSGS:
        text = _msg
        got = [m for m in messages if m["text"] == text]
        check(len(got) == 1 and got[0]["slot_utc"] == slot,
              "message %s (%s) recovered exactly once in slot %s"
              % (name, text, slot))
    check(all(m["slot_utc"] != NOISE_SLOT for m in messages),
          "noise-only slot %s yields zero messages" % NOISE_SLOT)
    check(len(messages) == 3,
          "total unique (slot, text) messages == 3 (got %d)"
          % len(messages))

    # Informational only: what naive file-aligned slicing does to C.
    print("\n[info] naive 15 s windows from file offset 0, C = "
          "'CQ T3ST JN58':")
    xf = np.frombuffer(mix.tobytes(), dtype=np.int16)
    for ws in (30, 45):
        seg = xf[ws * RATE:(ws + 15) * RATE]
        pth = os.path.join(tmp, "naive.wav")
        w = wave.open(pth, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(seg.tobytes())
        w.close()
        out = subprocess.run([DEC, pth], capture_output=True,
                             text=True).stdout
        hit = "CQ T3ST JN58" in out
        print("[info]   naive window [%2d,%2d): C %s"
              % (ws, ws + 15, "recovered" if hit else "NOT recovered"))

    if fails:
        print("\nRESULT: FAIL (%d assertion(s) failed)" % len(fails))
        return 1
    print("\nRESULT: PASS - slot alignment exact: A, B, C each once, "
          "in their true UTC slots; noise slot empty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
