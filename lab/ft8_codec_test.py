#!/usr/bin/env python3
"""Nature-Mirror Mesh — Lab Test 2: FT8 weak-signal codec round trip.

Pure-software test using PyFT8 (pip package):
  encode a standard FT8 message -> 79 8-FSK symbols -> build per-symbol
  soft probabilities (noise-free observation) -> run the library's LDPC
  decoder -> unpack -> compare with the original message.

This proves the *weak-signal coding chain* works offline; it is NOT an
over-the-air transmission. Full audio-file decode needs a live audio input
(PyFT8's Receiver binds a sound device via pyaudio/PortAudio, which is not
available in this sandbox).
"""
import sys
import types
import numpy as np

# PyFT8.receiver imports pyaudio at top level (live audio device path).
# pyaudio/PortAudio can't build in this sandbox; stub it so the *decoder*
# (pure numpy math) can be used offline.
sys.modules.setdefault("pyaudio", types.ModuleType("pyaudio"))

from PyFT8 import transmitter, receiver

# PyFT8 4.0.3 transmitter bug: pack_message calls add_call_hashes(),
# which only exists as receiver.add_call_hash(). Patch the name.
transmitter.add_call_hashes = receiver.add_call_hash

MSG = "CQ NMM1 AA00"

def main():
    symbols = transmitter.get_ft8_symbols(MSG)
    assert len(symbols) == 79, f"expected 79 symbols, got {len(symbols)}"

    # Build soft observation matrix p (79 x 8): correct tone gets high power.
    # receiver.decode() expects only the 58 payload symbols (the Receiver
    # class passes payload indexes 7..35 and 43..71; the 21 Costas/sync
    # symbols carry no message bits).
    p = np.full((79, 8), 0.1, dtype=np.float32)
    for idx, sym in enumerate(symbols):
        p[idx, sym] = 1.0
    payload_idxs = list(range(7, 36)) + list(range(43, 72))
    p_payload = p[payload_idxs]

    result, tag, llr_saved, ch_llr = receiver.decode(p_payload, 0)
    print(f"decoded: {result}  ({tag})")

    if result is None:
        print("RESULT: FAIL — LDPC decode did not converge")
        return 1

    # result is a tuple of decoded message fields; check the original call/grid appear
    joined = " ".join(str(x) for x in result if x)
    print(f"decoded fields: {joined}")
    if "NMM1" in joined and "AA00" in joined:
        print(f"RESULT: PASS — FT8 codec round trip: '{MSG}' encoded (79 symbols) and LDPC-decoded cleanly")
        return 0
    print("RESULT: FAIL — decoded content mismatch")
    return 1

if __name__ == "__main__":
    sys.exit(main())
