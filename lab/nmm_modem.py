#!/usr/bin/env python3
"""
Nature-Mirror Mesh — nmm_modem: a simple, robust digital modem for packet
data over an HF-like audio channel (baseband only; no RF is emitted by this
code — it produces/consumes WAV-rate samples at 12000 Hz).

WHY THIS EXISTS
---------------
The project's FT8 chain test (tx_chain_test.py) proved a short token beacon
can cross a simulated Watterson HF channel, but a real packed LXMF packet
(142 bytes) never crossed — FT8's structured 77-bit payload cannot carry
arbitrary packet bytes at any sane airtime. This modem is the invented
alternative: a purpose-built MFSK packet waveform that carries arbitrary
bytes, so the FULL LXMF packet itself crosses the channel.

WAVEFORM
--------
- 16-FSK, one nibble (4 bits) per symbol, non-coherent envelope detection.
- Tones: f_k = 525 + 100*k Hz for k = 0..15  (525..2025 Hz, inside the
  300-2800 Hz HF voice passband). 100 Hz spacing = 4 FFT bins at the
  40 ms symbol length, so adjacent-tone leakage is small even with the
  rectangular window, and a static two-path channel null (~667 Hz period
  for the project's 0.5/2.0 ms path pair) can only sit on a few tones.
- Symbol duration 40 ms (480 samples @ 12000 Hz) -> 25 sym/s, 100 bps raw.
  Justification: the channel's Doppler spread (sigma = 0.7 Hz) gives a
  coherence time of ~1 s, so a 40 ms symbol sees an essentially constant
  envelope (flat within a symbol) while 25 sym/s keeps the airtime of a
  ~150-byte packet near 25 s — acceptable for store-and-forward. Shorter
  symbols would buy speed but put more symbols inside each deep fade and
  widen each tone's noise bandwidth; longer symbols waste airtime for
  little extra energy per symbol at these SNRs.
- Each symbol is a pure tone burst with a 24-sample (2 ms) raised-cosine
  ramp at both ends to limit spectral splatter.

FRAMING
-------
[0.1 s silence] PREAMBLE(16 sym) SYNC(8 sym) HEADER(20 sym) DATA(...)
- PREAMBLE: tones alternate 0,15,0,15,... — a strong two-tone pattern the
  receiver correlates against to acquire symbol timing (sub-symbol phase
  search at 120-sample steps) and carrier frequency offset (search grid
  -50..+50 Hz in 6.25 Hz steps), tolerant to the specified +/-50 Hz.
- SYNC: fixed 8-symbol word [1,14,4,11,7,8,13,2]; the receiver requires
  >= 5/8 decided symbols to match (plus >= 13/16 preamble) before
  attempting the payload. Sync/preamble are acquisition aids only —
  individual sync symbols can themselves be faded (a +40 Hz offset run
  decided 5/8 sync symbols on a frame whose payload was fully valid),
  so frame VALIDITY is decided solely by RS decode + length agreement
  + CRC-32, which a false lock cannot plausibly satisfy.
- HEADER: payload length L as uint16 big-endian = 4 nibble symbols,
  transmitted 5 times; per-position majority vote on receive.
- DATA: the protected byte stream (below), 2 symbols per byte
  (high nibble first).

ERROR CONTROL
--------------
- Plain block: [L:2 bytes BE] + payload + CRC-32(payload) (zlib.crc32,
  4 bytes BE). A frame is accepted ONLY if the length fields agree AND
  the CRC-32 matches — never on partial evidence.
- FEC: Reed–Solomon over GF(256) (reedsolo), applied per chunk of
  K = 100 plain bytes with NSYM = 72 parity bytes -> 172-byte codewords.
  Per chunk the code corrects any mix of t unknown errors and e erasures
  with 2t + e <= 72 (i.e. up to 36 errors, or up to 72 erasures).
  Chunks are zero-padded to K before encoding (the true plain length is
  known from the header).
- Erasure decoding: the receiver measures each symbol's decision margin
  (strongest / second-strongest tone energy). Faded symbols are usually
  *detectably* weak, so any byte whose either symbol has margin < 1.6 is
  handed to the RS decoder as an erasure position — worth twice as much
  correction power as an unknown error. (Design history: without
  erasures, a -10 dB Watterson pass put 23-32 byte errors in each chunk,
  just over a 22-error budget; margins separate most errors from most
  good symbols, and NSYM = 72 absorbs the rest.)
- Detection: each symbol is decided from the single STFT frame that
  covers exactly that symbol (480 samples, rectangular window) — the
  channel's <= 2 ms multipath smear is 5% of a symbol, so neighbouring
  frames only dilute the measurement.
- Interleaving: codeword bytes are interleaved column-wise across chunks
  (byte i of every chunk in turn), so a time burst or a nulled tone
  region spreads its damage ~evenly across chunks instead of destroying
  one chunk outright.
- Code rate for a 142-byte packet: plain block = 148 bytes -> 2 chunks
  -> 344 protected bytes on air; rate = 142/344 = 0.41 before framing
  overhead, 142/366 = 0.39 including preamble/sync/header symbols.
  Total symbols for that packet: 16 + 8 + 20 + 688 = 732 -> 29.3 s of
  tones + 0.2 s silence = 29.5 s airtime (~4.8 payload bytes/s). Slow —
  deliberately; robustness is the design goal, and store-and-forward
  messaging tolerates it.

API
---
modem_encode(data: bytes) -> np.ndarray int16 (12000 Hz mono samples)
modem_decode(samples) -> bytes | None   (None = no valid frame / CRC fail)
"""

import zlib

import numpy as np

try:
    from reedsolo import RSCodec, ReedSolomonError
except ImportError:  # pragma: no cover
    RSCodec = None

FS = 12000
N_TONES = 16
TONE_BASE = 525.0
TONE_STEP = 100.0
TONES = TONE_BASE + TONE_STEP * np.arange(N_TONES)
SYM_LEN = 480                # 40 ms
RAMP = 24                    # 2 ms raised-cosine edges
LEAD_SILENCE = 1200          # 0.1 s
TRAIL_SILENCE = 1200

PREAMBLE = [0, 15] * 8                       # 16 symbols
SYNC = [1, 14, 4, 11, 7, 8, 13, 2]           # 8 symbols
HEADER_REPEATS = 5

RS_K = 100                   # plain bytes per RS chunk
RS_NSYM = 72                 # parity bytes per chunk (2t + e <= 72)
ERASURE_MARGIN = 1.6         # top1/top2 energy ratio below -> erasure
MAX_PAYLOAD = 4096

_RSC = RSCodec(RS_NSYM) if RSCodec is not None else None

# Receiver STFT parameters
STFT_WIN = 480
STFT_HOP = 120
STFT_N = 2048
DF_GRID_HZ = np.arange(-50.0, 50.01, 6.25)   # frequency-offset search grid


# ---------------------------------------------------------------------------
# FEC + framing (byte level)
# ---------------------------------------------------------------------------

def _rs_encode_chunk(chunk: bytes) -> bytes:
    out = _RSC.encode(chunk)
    return bytes(out[0]) if isinstance(out, tuple) else bytes(out)


def _rs_decode_chunk(codeword: bytes, erase_pos=None) -> bytes:
    out = _RSC.decode(codeword, erase_pos=erase_pos if erase_pos else None)
    return bytes(out[0]) if isinstance(out, tuple) else bytes(out)


def _protect(payload: bytes) -> bytes:
    """payload -> interleaved RS codeword bytes."""
    plain = len(payload).to_bytes(2, "big") + payload + \
        (zlib.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "big")
    n_chunks = (len(plain) + RS_K - 1) // RS_K
    codewords = []
    for c in range(n_chunks):
        chunk = plain[c * RS_K:(c + 1) * RS_K]
        chunk = chunk + bytes(RS_K - len(chunk))     # zero-pad to K
        codewords.append(_rs_encode_chunk(chunk))
    cw_len = RS_K + RS_NSYM
    out = bytearray()
    for i in range(cw_len):                          # column-wise interleave
        for c in range(n_chunks):
            out.append(codewords[c][i])
    return bytes(out)


def _unprotect(stream: bytes, payload_len: int, erasures=None):
    """Interleaved codeword bytes + expected payload length -> payload|None.
    `erasures` (optional) is a per-stream-byte 0/1 sequence aligned with
    `stream`; flagged positions are handed to the RS decoder as erasures."""
    plain_len = payload_len + 6
    n_chunks = (plain_len + RS_K - 1) // RS_K
    cw_len = RS_K + RS_NSYM
    if len(stream) < n_chunks * cw_len:
        return None
    stream = stream[:n_chunks * cw_len]
    codewords = [bytearray(cw_len) for _ in range(n_chunks)]
    erase_pos = [[] for _ in range(n_chunks)]
    pos = 0
    for i in range(cw_len):
        for c in range(n_chunks):
            codewords[c][i] = stream[pos]
            if erasures is not None and erasures[pos]:
                erase_pos[c].append(i)
            pos += 1
    plain = bytearray()
    for c in range(n_chunks):
        if len(erase_pos[c]) > RS_NSYM:
            return None
        try:
            plain += _rs_decode_chunk(bytes(codewords[c]), erase_pos[c])
        except ReedSolomonError:
            return None
    plain = bytes(plain[:plain_len])
    inner_len = int.from_bytes(plain[0:2], "big")
    if inner_len != payload_len:
        return None
    payload = plain[2:2 + payload_len]
    crc_stored = int.from_bytes(plain[2 + payload_len:6 + payload_len], "big")
    if (zlib.crc32(payload) & 0xFFFFFFFF) != crc_stored:
        return None
    return payload


def _bytes_to_symbols(data: bytes):
    syms = []
    for b in data:
        syms.append(b >> 4)
        syms.append(b & 0x0F)
    return syms


def _symbols_to_bytes(syms):
    out = bytearray()
    for i in range(0, len(syms) - 1, 2):
        out.append((syms[i] << 4) | syms[i + 1])
    return bytes(out)


# ---------------------------------------------------------------------------
# Waveform generation
# ---------------------------------------------------------------------------

def _tone_burst(tone_idx: int) -> np.ndarray:
    t = np.arange(SYM_LEN) / FS
    x = np.sin(2 * np.pi * TONES[tone_idx] * t)
    env = np.ones(SYM_LEN)
    ramp = 0.5 - 0.5 * np.cos(np.pi * np.arange(RAMP) / RAMP)
    env[:RAMP] = ramp
    env[-RAMP:] = ramp[::-1]
    return x * env


_BURSTS = [_tone_burst(k) for k in range(N_TONES)]


def frame_symbols(payload: bytes):
    """Full symbol sequence for a payload (preamble..data)."""
    header = _bytes_to_symbols(len(payload).to_bytes(2, "big"))
    syms = list(PREAMBLE) + list(SYNC) + header * HEADER_REPEATS
    syms += _bytes_to_symbols(_protect(payload))
    return syms


def modem_encode(data: bytes) -> np.ndarray:
    if _RSC is None:
        raise RuntimeError("reedsolo is required for modem_encode")
    if len(data) > MAX_PAYLOAD:
        raise ValueError(f"payload too large: {len(data)} > {MAX_PAYLOAD}")
    syms = frame_symbols(bytes(data))
    audio = np.concatenate([_BURSTS[s] for s in syms])
    out = np.concatenate([np.zeros(LEAD_SILENCE), audio,
                          np.zeros(TRAIL_SILENCE)])
    out = out * 0.85
    peak = np.max(np.abs(out))
    if peak > 1.0:
        out = out / peak
    return (out * 32767.0).astype(np.int16)


# ---------------------------------------------------------------------------
# Receiver
# ---------------------------------------------------------------------------

def _tone_energies(samples: np.ndarray):
    """STFT + per-(df, frame, tone) energies.

    Returns (E, ) where E has shape (n_df, n_frames, N_TONES); frame i
    covers samples [i*STFT_HOP, i*STFT_HOP + STFT_WIN).
    """
    x = samples.astype(np.float64)
    n_frames = max(0, (len(x) - STFT_WIN) // STFT_HOP + 1)
    idx = np.arange(STFT_WIN)[None, :] + STFT_HOP * np.arange(n_frames)[:, None]
    frames = x[np.minimum(idx, len(x) - 1)]
    spec = np.fft.rfft(frames, n=STFT_N, axis=1)
    power = (spec.real ** 2 + spec.imag ** 2)          # (frames, bins)
    bin_hz = FS / STFT_N
    E = np.empty((len(DF_GRID_HZ), n_frames, N_TONES))
    for di, df in enumerate(DF_GRID_HZ):
        for k in range(N_TONES):
            c = int(round((TONES[k] + df) / bin_hz))
            lo, hi = max(0, c - 2), min(power.shape[1], c + 3)
            E[di, :, k] = power[:, lo:hi].sum(axis=1)
    return E


def _symbol_energies(E_df, start_sample):
    """Energy vector for the symbol starting at start_sample (one df
    slice): the single STFT frame that starts exactly at the symbol —
    it covers precisely the symbol's 480 samples."""
    fi = start_sample // STFT_HOP
    if 0 <= fi < E_df.shape[0]:
        return E_df[fi].copy()
    return np.zeros(N_TONES)


def modem_decode(samples) -> bytes | None:
    if _RSC is None:
        return None
    x = np.asarray(samples)
    if len(x) < LEAD_SILENCE + SYM_LEN * 30:
        return None
    E = _tone_energies(x)

    # --- Acquisition: search start offset x frequency offset -------------
    best = None  # (score, start_sample, df_index)
    max_start = min(2880, len(x) - SYM_LEN * 44)
    for di in range(E.shape[0]):
        E_df = E[di]
        for start in range(0, max_start + 1, STFT_HOP):
            contrast = 0.0
            norm = 0.0
            for j, want in enumerate(PREAMBLE):
                other = 15 if want == 0 else 0
                ev = _symbol_energies(E_df, start + j * SYM_LEN)
                contrast += ev[want] - ev[other]
                norm += ev[want] + ev[other]
            if norm <= 0:
                continue
            pre_score = contrast / norm
            if pre_score < 0.25:
                continue
            sync_ratio = 0.0
            for j, want in enumerate(SYNC):
                ev = _symbol_energies(
                    E_df, start + (len(PREAMBLE) + j) * SYM_LEN)
                sync_ratio += np.log((ev[want] + 1e-9) /
                                     (ev.mean() + 1e-9))
            score = pre_score + 0.25 * sync_ratio
            if best is None or score > best[0]:
                best = (score, start, di)
    if best is None:
        return None
    _, start, di = best
    E_df = E[di]

    def decide(j):
        ev = _symbol_energies(E_df, start + j * SYM_LEN)
        return int(np.argmax(ev))

    # --- Verify preamble + sync on decided symbols ------------------------
    n_pre = len(PREAMBLE)
    pre_ok = sum(1 for j in range(n_pre) if decide(j) == PREAMBLE[j])
    sync_ok = sum(1 for j in range(len(SYNC))
                  if decide(n_pre + j) == SYNC[j])
    if pre_ok < 13 or sync_ok < 5:
        return None

    # --- Header: 5 repeats of 4 length symbols, majority vote ------------
    hdr0 = n_pre + len(SYNC)
    length_syms = []
    for pos in range(4):
        votes = [decide(hdr0 + r * 4 + pos) for r in range(HEADER_REPEATS)]
        length_syms.append(max(set(votes), key=votes.count))
    payload_len = int.from_bytes(_symbols_to_bytes(length_syms), "big")
    if payload_len > MAX_PAYLOAD:
        return None

    # --- Data symbols -----------------------------------------------------
    plain_len = payload_len + 6
    n_chunks = (plain_len + RS_K - 1) // RS_K
    n_data_bytes = n_chunks * (RS_K + RS_NSYM)
    data0 = hdr0 + 4 * HEADER_REPEATS
    total_needed = data0 + 2 * n_data_bytes
    n_symbols_avail = (len(x) - start) // SYM_LEN
    if n_symbols_avail < total_needed:
        return None
    data_syms = []
    erasures = []
    prev_margin = np.inf
    for j in range(2 * n_data_bytes):
        ev = _symbol_energies(E_df, start + (data0 + j) * SYM_LEN)
        top2 = np.partition(ev, -2)[-2:]
        margin = top2[1] / max(top2[0], 1e-12)
        data_syms.append(int(np.argmax(ev)))
        if j % 2 == 1:   # byte complete: erase if either symbol was weak
            erasures.append(1 if min(margin, prev_margin) < ERASURE_MARGIN
                            else 0)
        prev_margin = margin
    stream = _symbols_to_bytes(data_syms)
    return _unprotect(stream, payload_len, erasures)
