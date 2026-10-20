#!/usr/bin/env python3
"""
Nature-Mirror Mesh — DIGITAL LAB 1: FULL LXMF PACKET over the modem.

Question left open by tx_chain_test.py: there, only a short token beacon
crossed the simulated Watterson HF channel — the real packed LXMF packet
(142 bytes) never did, because FT8 cannot carry arbitrary packet bytes.
This test invents the alternative (lab/nmm_modem.py: a 16-FSK packet
modem with RS FEC + erasure decoding + interleaving) and asks whether
the FULL packed packet itself can cross the same channel, byte-exact.

PRE-REGISTERED SUCCESS CRITERION (stated here, before any run):
  In 10 independent trials at -10 dB full-band RMS SNR (fresh Watterson
  channel seed AND fresh LXMF packet per trial), at least 8 of 10
  packets must be recovered BYTE-EXACT (SHA-256 match) by the modem.
  The SNR sweep (0 / -5 / -10 / -15 dB, one run each) and a +40 Hz
  offset run are reported but are NOT part of the criterion.

Packet production mirrors tx_chain_test.py exactly: node B builds a REAL
LXMF.LXMessage addressed to node A's real delivery destination (A's
identity reconstructed from its published public key via
Identity.load_public_key), with a fresh unique token as content, and
packs it; the packed bytes (msg.packed) are what crosses the channel.
Channel: tx_chain_test.apply_channel with its documented parameters
(two paths 0.5 ms / 2.0 ms, powers 0.6 / 0.4, Rayleigh envelopes,
Gaussian Doppler sigma = 0.7 Hz, AWGN to the target full-band RMS SNR).
Receiver-side, every byte-exact recovery is additionally validated at
the LXMF level with LXMF.LXMessage.unpack_from_bytes: the unpacked
message's content must equal the original token.

HONEST SCOPE: baseband audio + simulated channel model only; no RF was
emitted and nothing was transmitted over the air.

Usage:  python modem_packet_test.py             (orchestrated test)
        python modem_packet_test.py produce DIR (worker: build packets)
"""

import hashlib
import json
import os
import random
import shutil
import string
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "results")
WORK = os.path.join(BASE, "modem_work")
sys.path.insert(0, BASE)

import nmm_modem as modem          # noqa: E402
import tx_chain_test as tct        # noqa: E402  (channel + config helpers)

FS = 12000
SWEEP_SNRS = [0.0, -5.0, -10.0, -15.0]
SWEEP_SEED_BASE = 20261101
RELIABILITY_SNR = -10.0
RELIABILITY_TRIALS = 10
RELIABILITY_SEED_BASE = 20261201
CRITERION_MIN = 8                  # >= 8/10 byte-exact at -10 dB
OFFSET_RUN = (-10.0, 40, 20261199)  # (snr, offset Hz, seed) — bonus

LOG_LINES = []


def log(msg=""):
    print(msg, flush=True)
    LOG_LINES.append(str(msg))


# ---------------------------------------------------------------------------
# Packet production (worker subprocess; mirrors tx_chain_test.py's sender)
# ---------------------------------------------------------------------------

def produce(workdir):
    import RNS
    import LXMF

    os.makedirs(workdir, exist_ok=True)
    configdir = os.path.join(workdir, "node_b")
    tct.write_config(configdir)
    storage = os.path.join(workdir, "storage_b")
    os.makedirs(storage, exist_ok=True)

    # Node A exists here only as an identity: its published public key is
    # all the sender needs (exactly as in tx_chain_test.py).
    identity_a = RNS.Identity()

    RNS.Reticulum(configdir=configdir)
    identity_b = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity_b, storagepath=storage)
    source = router.register_delivery_identity(
        identity_b, display_name="NMM Node B (modem test)", stamp_cost=None)

    dest_identity = RNS.Identity(create_keys=False)
    dest_identity.load_public_key(identity_a.get_public_key())
    dest = RNS.Destination(dest_identity, RNS.Destination.OUT,
                           RNS.Destination.SINGLE, "lxmf", "delivery")

    rng = random.Random(20261020)
    packets = []
    pkt_dir = os.path.join(workdir, "packets")
    os.makedirs(pkt_dir, exist_ok=True)
    n_packets = 1 + RELIABILITY_TRIALS
    for i in range(n_packets):
        suffix = "".join(rng.choice(string.ascii_uppercase + string.digits)
                         for _ in range(12))
        token = f"NMM-MODEM-{suffix}"
        msg = LXMF.LXMessage(dest, source, content=token,
                             title="nmm-modem-test")
        msg.pack()
        packed = bytes(msg.packed)
        path = os.path.join(pkt_dir, f"packet_{i:02d}.bin")
        with open(path, "wb") as f:
            f.write(packed)
        packets.append({
            "index": i,
            "token": token,
            "file": path,
            "packed_len": len(packed),
            "sha256": hashlib.sha256(packed).hexdigest(),
            "lxmf_message_hash": RNS.hexrep(msg.hash, delimit=False),
        })
        print(f"[producer] packet {i}: token={token} "
              f"packed={len(packed)} B sha256={packets[-1]['sha256'][:16]}...",
              flush=True)
    with open(os.path.join(workdir, "packets.json"), "w") as f:
        json.dump(packets, f, indent=2)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_one(packed: bytes, snr_db: float, offset_hz: int, seed: int):
    """Encode -> Watterson channel -> decode. Returns (recovered|None, secs)."""
    enc = modem.modem_encode(packed)
    x = enc.astype(np.float64)
    x = x * (6000.0 / np.sqrt(np.mean(x ** 2)))   # same level as tx tests
    rx, _meta = tct.apply_channel(x, snr_db, offset_hz, seed)
    t0 = time.time()
    recovered = modem.modem_decode(rx)
    return recovered, len(enc) / FS, time.time() - t0


def orchestrate():
    os.makedirs(RESULTS, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK, exist_ok=True)

    log("=== Nature-Mirror Mesh — DIGITAL LAB 1: full LXMF packet "
        "over nmm_modem ===")
    log("Pre-registered criterion: >= "
        f"{CRITERION_MIN}/{RELIABILITY_TRIALS} byte-exact recoveries at "
        f"{RELIABILITY_SNR:+.0f} dB (fresh packet + fresh channel seed "
        "per trial). Sweep and offset runs are reported, not gated.")
    log("")

    # --- Produce real packed LXMF packets (worker subprocess) -----------
    prod = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "produce", WORK],
        capture_output=True, text=True, timeout=600)
    log(prod.stdout.strip())
    if prod.returncode != 0:
        log(f"PRODUCER FAILED rc={prod.returncode}\n{prod.stderr[-2000:]}")
        _write_outputs(None, None, None, None, verdict=False)
        return 1
    with open(os.path.join(WORK, "packets.json")) as f:
        packets = json.load(f)
    for p in packets:
        with open(p["file"], "rb") as f:
            p["bytes"] = f.read()
        assert hashlib.sha256(p["bytes"]).hexdigest() == p["sha256"]

    sweep_pkt = packets[0]
    airtime = len(modem.modem_encode(sweep_pkt["bytes"])) / FS
    log("")
    log(f"Sweep packet: token={sweep_pkt['token']} "
        f"packed={sweep_pkt['packed_len']} B "
        f"sha256={sweep_pkt['sha256']}")
    log(f"Modem airtime per packet: {airtime:.1f} s "
        f"({len(modem.frame_symbols(sweep_pkt['bytes']))} symbols); "
        f"effective throughput = {sweep_pkt['packed_len'] / airtime:.2f} "
        "payload bytes/s")
    log("")

    # --- LXMF-level validator (this process) ------------------------------
    import RNS
    import LXMF
    val_cfg = os.path.join(WORK, "validator")
    tct.write_config(val_cfg)
    RNS.Reticulum(configdir=val_cfg)

    def lxmf_validate(recovered: bytes, pkt: dict):
        """Receiver-side LXMF validation of recovered bytes: the message
        must unpack, its content must equal the token (unpack returns
        content as bytes), and its recomputed LXMF message hash must
        equal the hash the producer recorded at pack time."""
        try:
            m = LXMF.LXMessage.unpack_from_bytes(recovered)
            if m is None:
                return False
            content = m.content
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            return content == pkt["token"] and \
                RNS.hexrep(m.hash, delimit=False) == pkt["lxmf_message_hash"]
        except Exception as e:  # noqa: BLE001
            log(f"    LXMF unpack raised: {type(e).__name__}: {e}")
            return False

    # --- SNR sweep ---------------------------------------------------------
    log("--- SNR sweep (sweep packet, fresh channel seed per level) ---")
    sweep_rows = []
    for i, snr in enumerate(SWEEP_SNRS):
        rec, _at, dt = run_one(sweep_pkt["bytes"], snr, 0,
                               SWEEP_SEED_BASE + i)
        exact = rec is not None and \
            hashlib.sha256(rec).hexdigest() == sweep_pkt["sha256"]
        lx = lxmf_validate(rec, sweep_pkt) if exact else False
        sweep_rows.append((snr, exact, lx))
        log(f"  SNR {snr:+.0f} dB: byte-exact={'YES' if exact else 'NO'} "
            f"lxmf-valid={'YES' if lx else 'NO'} (decode {dt:.1f} s)")

    # --- Bonus: frequency-offset run --------------------------------------
    snr_o, off_o, seed_o = OFFSET_RUN
    rec, _at, dt = run_one(sweep_pkt["bytes"], snr_o, off_o, seed_o)
    offset_exact = rec is not None and \
        hashlib.sha256(rec).hexdigest() == sweep_pkt["sha256"]
    log(f"  BONUS offset {off_o:+d} Hz @ {snr_o:+.0f} dB: "
        f"byte-exact={'YES' if offset_exact else 'NO'} (decode {dt:.1f} s)")
    log("")

    # --- Reliability: 10 trials at -10 dB ----------------------------------
    log(f"--- Reliability: {RELIABILITY_TRIALS} trials @ "
        f"{RELIABILITY_SNR:+.0f} dB (fresh packet + seed per trial) ---")
    trial_rows = []
    n_exact = 0
    n_lxmf = 0
    for t in range(RELIABILITY_TRIALS):
        p = packets[1 + t]
        rec, _at, dt = run_one(p["bytes"], RELIABILITY_SNR, 0,
                               RELIABILITY_SEED_BASE + t)
        exact = rec is not None and \
            hashlib.sha256(rec).hexdigest() == p["sha256"]
        lx = lxmf_validate(rec, p) if exact else False
        n_exact += 1 if exact else 0
        n_lxmf += 1 if lx else 0
        trial_rows.append((t + 1, p["token"], p["packed_len"], exact, lx))
        log(f"  trial {t + 1:2d}: token={p['token']} "
            f"packed={p['packed_len']} B byte-exact="
            f"{'YES' if exact else 'NO'} lxmf-valid={'YES' if lx else 'NO'} "
            f"(decode {dt:.1f} s)")
    log("")
    criterion_met = n_exact >= CRITERION_MIN
    log(f"RELIABILITY: {n_exact}/{RELIABILITY_TRIALS} byte-exact at "
        f"{RELIABILITY_SNR:+.0f} dB; {n_lxmf}/{RELIABILITY_TRIALS} "
        "LXMF-validated")
    log(f"CRITERION ({CRITERION_MIN}/{RELIABILITY_TRIALS}): "
        f"{'MET' if criterion_met else 'NOT MET'}")
    log(f"RESULT: {'PASS' if criterion_met else 'FAIL'}")

    _write_outputs(packets, sweep_rows, trial_rows,
                   (airtime, offset_exact), verdict=criterion_met)
    return 0 if criterion_met else 1


def _write_outputs(packets, sweep_rows, trial_rows, extra, verdict):
    with open(os.path.join(RESULTS, "modem_packet_test.log"), "w") as f:
        f.write("\n".join(LOG_LINES) + "\n")
    if packets is None:
        return
    airtime, offset_exact = extra
    p0 = packets[0]
    lines = []
    lines.append("# Full LXMF Packet over nmm_modem — Results "
                 "(DIGITAL LAB 1)")
    lines.append("")
    lines.append(f"Date (UTC): "
                 f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Question")
    lines.append("tx_chain_test.py proved a token *beacon* can cross a "
                 "simulated Watterson HF channel, but the real packed "
                 "LXMF packet never crossed it (FT8 cannot carry "
                 "arbitrary packet bytes). This test runs the invented "
                 "alternative — lab/nmm_modem.py — and asks whether the "
                 "FULL packed packet crosses, byte-exact.")
    lines.append("")
    lines.append("## Pre-registered criterion")
    lines.append(f">= {CRITERION_MIN}/{RELIABILITY_TRIALS} byte-exact "
                 f"recoveries at {RELIABILITY_SNR:+.0f} dB, fresh LXMF "
                 "packet and fresh channel seed per trial. Stated in "
                 "the test header before any run.")
    lines.append("")
    lines.append("## Modem (nmm_modem.py)")
    lines.append("16-FSK (525-2025 Hz, 100 Hz spacing), 40 ms symbols "
                 "(100 bps raw), non-coherent detection on the "
                 "symbol-aligned STFT frame; preamble + sync acquisition "
                 "over a +/-50 Hz offset grid; 5x-repeated length "
                 "header; plain block = length + payload + CRC-32; "
                 "Reed-Solomon (K=100, NSYM=72, 2t+e<=72 with "
                 "margin-based erasure decoding, threshold 1.6) with "
                 "column interleaving across chunks.")
    lines.append("")
    lines.append(f"- Sweep packet: token `{p0['token']}`, packed "
                 f"{p0['packed_len']} bytes, "
                 f"SHA-256 `{p0['sha256']}`")
    lines.append(f"- LXMF message hash: `{p0['lxmf_message_hash']}`")
    lines.append(f"- Airtime per packet: {airtime:.1f} s; effective "
                 f"throughput {p0['packed_len'] / airtime:.2f} payload "
                 "bytes/s (store-and-forward tolerates this; HF "
                 "messaging is not a streaming medium)")
    lines.append("")
    lines.append("## Channel")
    lines.append("tx_chain_test.apply_channel, unchanged: two paths "
                 "(0.5 ms / 2.0 ms, powers 0.6 / 0.4), Rayleigh "
                 "envelopes, Gaussian Doppler sigma = 0.7 Hz, AWGN to "
                 "the target full-band RMS SNR.")
    lines.append("")
    lines.append("## SNR sweep (one run per level, same packet)")
    lines.append("")
    lines.append("| SNR (full-band RMS) | Byte-exact | LXMF-valid |")
    lines.append("|---|---|---|")
    for snr, exact, lx in sweep_rows:
        lines.append(f"| {snr:+.0f} dB | {'YES' if exact else 'NO'} | "
                     f"{'YES' if lx else 'NO'} |")
    lines.append("")
    lines.append(f"Bonus run: +40 Hz frequency offset at "
                 f"{OFFSET_RUN[0]:+.0f} dB — byte-exact: "
                 f"{'YES' if offset_exact else 'NO'} (not gated).")
    lines.append("")
    lines.append(f"## Reliability @ {RELIABILITY_SNR:+.0f} dB "
                 "(fresh packet + seed per trial)")
    lines.append("")
    lines.append("| Trial | Token | Packed bytes | Byte-exact | "
                 "LXMF-valid |")
    lines.append("|---|---|---|---|---|")
    for n, token, plen, exact, lx in trial_rows:
        lines.append(f"| {n} | `{token}` | {plen} | "
                     f"{'YES' if exact else 'NO'} | "
                     f"{'YES' if lx else 'NO'} |")
    lines.append("")
    n_exact = sum(1 for r in trial_rows if r[3])
    n_lxmf = sum(1 for r in trial_rows if r[4])
    lines.append(f"Byte-exact: **{n_exact}/{len(trial_rows)}**; "
                 f"LXMF-validated: **{n_lxmf}/{len(trial_rows)}**.")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{'PASS' if verdict else 'FAIL'}** — pre-registered "
                 f"criterion >= {CRITERION_MIN}/{RELIABILITY_TRIALS} "
                 f"byte-exact at {RELIABILITY_SNR:+.0f} dB: "
                 f"{'met' if verdict else 'NOT met'} "
                 f"({n_exact}/{len(trial_rows)}).")
    lines.append("")
    lines.append("## Attempt history")
    lines.append("Attempt 1 (preserved as modem_packet_test_attempt1.log "
                 "/ MODEM_PACKET_TEST_attempt1.md) already met the "
                 "byte-level criterion (10/10 at -10 dB), but its LXMF "
                 "column read NO throughout: the validator compared "
                 "unpack_from_bytes' bytes content against a str token "
                 "(a test-harness type bug, not a data failure — the "
                 "unpacked content and LXMF message hash in fact match). "
                 "Attempt 1's bonus offset run also failed at the "
                 "receiver's sync gate (5/8 sync symbols decided on a "
                 "frame whose payload was valid). Attempt 2 (this file) "
                 "fixes the validator (bytes-aware content comparison "
                 "+ LXMF message-hash equality) and relaxes the sync "
                 "gate to >= 5/8, with RS + length + CRC-32 remaining "
                 "the sole arbiters of frame validity. All gated "
                 "numbers above are from attempt 2, run end-to-end "
                 "after the fixes.")
    lines.append("")
    lines.append("## Honest scope")
    lines.append("Baseband audio + a simulated channel model; **no RF "
                 "was emitted** and nothing was transmitted over the "
                 "air. What crossed the simulated channel in this test "
                 "is the complete packed LXMF packet itself (unlike "
                 "the FT8 beacon test, where only message content "
                 "crossed as a token). The remaining physical step is "
                 "unchanged: feed this modem's audio to a real SSB "
                 "transmitter / receive it on a real receiver, which "
                 "requires licensed hardware.")
    lines.append("")
    with open(os.path.join(RESULTS, "MODEM_PACKET_TEST.md"), "w") as f:
        f.write("\n".join(lines))
    log("Wrote lab/results/modem_packet_test.log + MODEM_PACKET_TEST.md")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "produce":
        produce(sys.argv[2])
    else:
        sys.exit(orchestrate())
