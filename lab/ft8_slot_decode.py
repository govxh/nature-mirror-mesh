#!/usr/bin/env python3
"""
Nature-Mirror Mesh -- UTC-slot-aligned FT8 decoder (audit fix, 2026-10-20).

WHY THIS EXISTS
---------------
The original decode approach (kiwisdr.yml heredoc / oracle_score.py) sliced
a recording into 15 s windows at a 2 s stride from an ARBITRARY file start
and deduplicated by message text across the whole recording. That is
wasteful (38 decode_ft8 runs for 90 s of audio), boundary-sloppy (the same
transmission is decoded 2-3 times from overlapping windows and merged by
text, so repeated transmissions of the same text in different slots are
silently collapsed into one), and it cannot attribute a message to its
actual UTC slot.

This decoder instead aligns windows to the true FT8 slot grid: FT8 slots
are 15 s long and start at UTC :00/:15/:30/:45. Given the recording start
time (UTC, ISO 8601), it computes

    offset_to_first_slot = (15 - (start_epoch mod 15)) mod 15   [seconds]

and decodes each UTC-aligned 15 s slot exactly ONCE. The final slot, if
the recording ends inside it, is zero-padded to 15 s and marked PARTIAL.
Deduplication is only within a slot: identical (slot, text) pairs are
collapsed; the same text in two different slots is reported twice,
because it IS two transmissions.

OUTPUT (stdout)
---------------
Comment lines start with '#': WAV facts, per-slot headers (slot UTC,
FULL or PARTIAL + audio seconds present), and a final summary.
One line per decoded message:

    <slot_utc_iso>  <dt_s>  <freq_hz>  <text>

e.g.  2026-10-20T07:57:30Z  +1.36  291  CQ IW2NEF JN46

dt/freq are decode_ft8's own reported values (dt is relative to the
slot's window start). A message's approximate absolute UTC is
slot_utc + dt.

USAGE
-----
    python3 ft8_slot_decode.py RECORDING.wav 2026-10-20T07:57:25Z \
        [--decode-ft8 PATH] [--min-slot-frac 0.5]

Also importable: decode_slots(wav_path, start_utc_iso, decode_ft8) ->
list of dicts {slot_utc, dt, freq_hz, text, partial}.
Receive-only: this program never transmits anything.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timedelta, timezone

import numpy as np

SLOT_S = 15.0
MSG_RE = re.compile(
    r"^\d{6}\s+[+-]\d+\.\d\s+([+-]\d+\.\d\d)\s+(\d+)\s+~\s+(.*?)\s*$")


def parse_start_utc(s):
    """Parse ISO 8601 (with 'Z' or offset, fractional seconds allowed)
    to an aware UTC datetime."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def slot_decode(wav_path, start_utc_iso, decode_ft8):
    """Decode a WAV in UTC-aligned 15 s slots. Yields (header_lines,
    messages) where messages are dicts with keys slot_utc (ISO str),
    dt (float, s), freq_hz (int), text (str), partial (bool)."""
    start_dt = parse_start_utc(start_utc_iso)
    start_epoch = start_dt.timestamp()

    w = wave.open(wav_path, "rb")
    nch, sw, rate, n = (w.getnchannels(), w.getsampwidth(),
                        w.getframerate(), w.getnframes())
    raw = w.readframes(n)
    w.close()
    if sw != 2:
        raise ValueError("expected 16-bit WAV, got sampwidth=%d" % sw)
    x = np.frombuffer(raw, dtype=np.int16)
    if nch > 1:
        x = x[::nch]
    x = x.astype(np.float64)
    headers = []
    headers.append("WAV: %d Hz, %d channel(s), 16-bit, %d samples, "
                   "%.2f s" % (rate, nch, len(x), len(x) / float(rate)))
    if rate != 12000:
        m = int(round(len(x) * 12000.0 / rate))
        x = np.interp(np.arange(m) * rate / 12000.0,
                      np.arange(len(x)), x)
        headers.append("Resampled %d -> 12000 Hz (decode_ft8 expects "
                       "12000 Hz mono)" % rate)
        rate = 12000
    x = np.clip(x, -32767, 32767).astype(np.int16)
    dur = len(x) / float(rate)

    offset = (SLOT_S - (start_epoch % SLOT_S)) % SLOT_S
    headers.append("Recording start (UTC): %s" % start_dt.strftime(
        "%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")
    headers.append("Offset to first UTC slot boundary: %.2f s" % offset)

    win = int(SLOT_S * rate)
    messages = []
    slot_idx = 0
    pos = offset
    while pos < dur - 1e-9:
        slot_start_epoch = start_epoch + pos
        slot_dt = datetime.fromtimestamp(slot_start_epoch,
                                         tz=timezone.utc)
        slot_iso = slot_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        s0 = int(round(pos * rate))
        seg = x[s0:s0 + win]
        have = len(seg) / float(rate)
        partial = have < SLOT_S - 1e-6
        if partial:
            seg = np.pad(seg, (0, win - len(seg)))
        headers.append("Slot %s (%s, %.1f s of audio%s)"
                       % (slot_iso, "PARTIAL" if partial else "FULL",
                          have, ", zero-padded" if partial else ""))
        with tempfile.NamedTemporaryFile(suffix=".wav",
                                         delete=False) as tf:
            tmp = tf.name
        try:
            wo = wave.open(tmp, "wb")
            wo.setnchannels(1)
            wo.setsampwidth(2)
            wo.setframerate(rate)
            wo.writeframes(seg.astype(np.int16).tobytes())
            wo.close()
            p = subprocess.run([decode_ft8, tmp], capture_output=True,
                               text=True)
        finally:
            os.unlink(tmp)
        seen = set()
        for ln in p.stdout.splitlines():
            m = MSG_RE.match(ln)
            if not m:
                continue
            dt_v, freq_v, text = float(m.group(1)), int(m.group(2)), \
                m.group(3)
            if text in seen:
                continue
            seen.add(text)
            messages.append({"slot_utc": slot_iso, "dt": dt_v,
                             "freq_hz": freq_v, "text": text,
                             "partial": partial})
        slot_idx += 1
        pos = offset + slot_idx * SLOT_S
    return headers, messages


def main():
    ap = argparse.ArgumentParser(description="UTC-slot-aligned FT8 "
                                             "decoder (ft8_lib).")
    ap.add_argument("wav", help="recording WAV (12000 Hz mono expected)")
    ap.add_argument("start_utc", help="recording start time, ISO 8601 "
                                      "UTC, e.g. 2026-10-20T07:57:25Z")
    ap.add_argument("--decode-ft8", default=None,
                    help="path to ft8_lib decode_ft8 (default: "
                         "alongside this script in ft8_lib/)")
    args = ap.parse_args()
    decode_ft8 = args.decode_ft8 or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ft8_lib",
        "decode_ft8")
    headers, messages = slot_decode(args.wav, args.start_utc, decode_ft8)
    for h in headers:
        print("# " + h)
    for msg in messages:
        print("%s  %+0.2f  %d  %s" % (msg["slot_utc"], msg["dt"],
                                      msg["freq_hz"], msg["text"]))
    print("# Unique (slot, text) messages: %d" % len(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
