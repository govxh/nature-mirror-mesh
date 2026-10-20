#!/usr/bin/env python3
"""
Nature-Mirror Mesh — DIGITAL LAB 3 (Part 1): LONG MESSAGES OVER THE
SIMULATED-RADIO MESH.

Question
--------
DIGITAL LAB 2 (modem_mesh_test.py) proved a short LXMF message
(a ~150 B packed packet) crosses a two-hop mesh where every link is
the nmm_modem over a simulated Watterson HF channel at -10 dB per hop.
Real chat messages are longer than a token. This test measures the
SIZE ENVELOPE of that same mesh: LXMF messages with content of
~500 B and ~1500 B, delivered S -> T -> C over the identical setup
(same ModemInterface, same channel, frame_repeats = 3, -10 dB per
hop). LXMF/Reticulum handle the larger payloads natively (link
establishment + resource transfer when the message no longer fits
the opportunistic single-packet path); nothing in the stack is
special-cased for this test. The job here is to run it, measure,
and report honestly.

PRE-REGISTERED SUCCESS CRITERION (stated here, before any run):
    PASS (per size) = the message is delivered with content bytes
    AND LXMF message hash validated at C (received content SHA-256
    == sent content SHA-256, received LXMF hash == sent LXMF hash,
    received length == sent length) within 2 end-to-end attempts
    for that size. An "end-to-end attempt" is one full orchestrated
    run: fresh node processes S/T/C, one LXMF message.
    OVERALL PASS = both 500 B and 1500 B pass.
    If a size fails both attempts, a size descent runs
    (1000 B, then 750 B; 2 attempts each) and the deliverable is
    the measured envelope: the largest size that passed, with all
    failures reported, not hidden.

Design notes
------------
- Content: exact-length byte strings — an ASCII header
  ("NMM-LONGMSG-<size>B-") followed by seeded pseudo-random bytes
  (seed fixed per size, so the test is reproducible). LXMF packs
  and encrypts as usual; the modem sees only encrypted RNS packets.
- Every attempt uses a fresh work directory and fresh node
  processes, reusing modem_mesh_test.py's topology, configs,
  announce/path machinery and per-hop stats accounting verbatim in
  spirit (same spool "air", same seeds, same frame_repeats = 3).
- Metrics reported per attempt: verdict, wall time, total simulated
  airtime (sum over hops of frame airtimes from interface stats),
  frames transmitted per hop, retransmitted frames, the sender's
  LXMF delivery_attempts counter, max RNS packet seen, and whether
  S reached router state DELIVERED (the proof crossing both hops
  back). Simulated airtime is what the frames would occupy on a
  real ~40 bit/s HF link; wall clock is CPU time and is much
  shorter.

HONEST SCOPE: baseband audio + simulated channel models only; no
RF was emitted, nothing was transmitted over the air, and no
TCP/UDP exists between the nodes.

Usage:  python longmsg_mesh_test.py              (500 B, then 1500 B,
                                                  descent if needed)
        python longmsg_mesh_test.py 500          (one size only)
        python longmsg_mesh_test.py transport <workdir>
        python longmsg_mesh_test.py receiver  <workdir>
        python longmsg_mesh_test.py sender    <workdir> <size>
"""

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "results")
WORK_ROOT = os.path.join(BASE, "longmsg_work")
LOG_PATH = os.path.join(RESULTS, "longmsg_mesh_test.log")
MD_PATH = os.path.join(RESULTS, "LONGMSG_TEST.md")

SNR_DB = -10.0
ANNOUNCE_INTERVAL = 15          # seconds between C announces
PATH_REQUEST_INTERVAL = 15      # seconds between S path requests
MAX_ATTEMPTS = 2                # pre-registered: per size
SIZES_DEFAULT = [500, 1500]
DESCENT = [1000, 750]           # tried only if 1500 fails both attempts

# Per-attempt deadlines (wall clock seconds). Wall clock here is CPU
# time; the simulated airtime of a long message is far larger.
PATH_DEADLINE = 900
DELIVERY_DEADLINE = 2400
RECEIVER_DEADLINE = 3300
TRANSPORT_DEADLINE = 3450
ORCH_SENDER_WAIT = 3350


def air_dirs(work):
    return {
        "st": os.path.join(work, "air", "s_to_t"),
        "ts": os.path.join(work, "air", "t_to_s"),
        "tc": os.path.join(work, "air", "t_to_c"),
        "ct": os.path.join(work, "air", "c_to_t"),
    }


SEEDS = {"st": 3301, "ts": 3302, "tc": 3303, "ct": 3304}


def make_content(size):
    """Deterministic exact-length content for a given size."""
    prefix = f"NMM-LONGMSG-{size}B-".encode()
    rng = random.Random(20261020 + size)
    body = rng.randbytes(size - len(prefix))
    content = prefix + body
    assert len(content) == size
    return content


def stats_path(work, name):
    return os.path.join(work, f"stats_{name}.jsonl")


def write_config(work, configdir, role):
    air = air_dirs(work)
    os.makedirs(os.path.join(configdir, "interfaces"), exist_ok=True)
    shutil.copy(os.path.join(BASE, "modem_interface.py"),
                os.path.join(configdir, "interfaces",
                             "ModemInterface.py"))

    def iface_section(name, tx_key, rx_key, stats_name):
        return f"""  [[{name}]]
    type = ModemInterface
    enabled = True
    tx_dir = {air[tx_key]}
    rx_dir = {air[rx_key]}
    stats_path = {stats_path(work, stats_name)}
    lab_dir = {BASE}
    link_seed = {SEEDS[tx_key]}
    snr_db = {SNR_DB}
    frame_repeats = 3"""

    if role == "transport":
        ifaces = "\n\n".join([
            iface_section("Modem link to S", "ts", "st", "t_facing_s"),
            iface_section("Modem link to C", "tc", "ct", "t_facing_c")])
        transport = "True"
    elif role == "receiver":
        ifaces = iface_section("Modem link to T", "ct", "tc", "c")
        transport = "False"
    else:  # sender
        ifaces = iface_section("Modem link to T", "st", "ts", "s")
        transport = "False"

    cfg = f"""[reticulum]
  enable_transport = {transport}
  share_instance = False
  panic_on_interface_error = False

[logging]
  loglevel = {os.environ.get("NMM_LOGLEVEL", "4")}

[interfaces]
{ifaces}
"""
    with open(os.path.join(configdir, "config"), "w") as f:
        f.write(cfg)


# ----------------------------------------------------------------------
# Workers
# ----------------------------------------------------------------------

def run_transport(workdir):
    import RNS

    configdir = os.path.join(workdir, "node_t")
    write_config(workdir, configdir, "transport")
    RNS.Reticulum(configdir=configdir)
    print(f"[T] transport node up (modem interfaces only), transport "
          f"identity {RNS.hexrep(RNS.Transport.identity.hash, delimit=False)}",
          flush=True)

    dest_file = os.path.join(workdir, "dest_hash.txt")
    received_file = os.path.join(workdir, "received.json")
    deadline = time.time() + TRANSPORT_DEADLINE
    reported = False
    while time.time() < deadline:
        if os.path.exists(dest_file) and not reported:
            dest_hash = bytes.fromhex(open(dest_file).read().strip())
            if RNS.Transport.has_path(dest_hash):
                print(f"[T] learned path to C over modem hop: "
                      f"hops_to(C)={RNS.Transport.hops_to(dest_hash)} "
                      f"(1 = C is one modem hop from T)", flush=True)
                with open(os.path.join(workdir, "t_hops.json"), "w") as f:
                    json.dump({"hops_to_c":
                               RNS.Transport.hops_to(dest_hash)}, f)
                reported = True
        if os.path.exists(received_file):
            print("[T] relay job done (C received the message); T "
                  "forwarded traffic between S and C over modem hops",
                  flush=True)
            time.sleep(5)
            sys.exit(0)
        time.sleep(1)
    print("[T] TIMEOUT", flush=True)
    sys.exit(2)


def run_receiver(workdir):
    import RNS
    import LXMF

    configdir = os.path.join(workdir, "node_c")
    write_config(workdir, configdir, "receiver")
    storage = os.path.join(workdir, "storage_c")
    os.makedirs(storage, exist_ok=True)

    RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    delivery = router.register_delivery_identity(
        identity, display_name="NMM Node C (longmsg mesh)",
        stamp_cost=None)
    router.register_delivery_callback(
        lambda m: on_message(m, workdir))

    with open(os.path.join(workdir, "dest_hash.txt"), "w") as f:
        f.write(RNS.hexrep(delivery.hash, delimit=False))
    print(f"[C] delivery destination: "
          f"{RNS.hexrep(delivery.hash, delimit=False)}", flush=True)

    received_file = os.path.join(workdir, "received.json")
    deadline = time.time() + RECEIVER_DEADLINE
    while time.time() < deadline and not os.path.exists(received_file):
        router.announce(delivery.hash)
        print("[C] announced over modem hop (will propagate "
              "C -> T -> S)", flush=True)
        time.sleep(ANNOUNCE_INTERVAL)

    if os.path.exists(received_file):
        print("[C] message received and written to file", flush=True)
        time.sleep(3)
        sys.exit(0)
    print("[C] TIMEOUT waiting for message", flush=True)
    sys.exit(2)


def on_message(message, workdir):
    import RNS
    print("[C] delivery callback invoked", flush=True)
    content = bytes(message.content)
    msg_hash = RNS.hexrep(message.hash, delimit=False)
    sha = hashlib.sha256(content).hexdigest()
    print(f"[C] DECRYPTED MESSAGE RECEIVED (via 2 modem hops): "
          f"{len(content)} bytes, sha256={sha}", flush=True)
    print(f"[C] LXMF message hash: {msg_hash}", flush=True)
    with open(os.path.join(workdir, "received_content.bin"), "wb") as f:
        f.write(content)
    with open(os.path.join(workdir, "received.json"), "w") as f:
        json.dump({"content_len": len(content),
                   "content_sha256": sha,
                   "lxmf_hash": msg_hash,
                   "source_hash": RNS.hexrep(message.source_hash,
                                             delimit=False)}, f)


def run_sender(workdir, size):
    import RNS
    import LXMF

    configdir = os.path.join(workdir, "node_s")
    write_config(workdir, configdir, "sender")
    storage = os.path.join(workdir, "storage_s")
    os.makedirs(storage, exist_ok=True)

    content = make_content(size)
    content_sha = hashlib.sha256(content).hexdigest()
    dest_hash = bytes.fromhex(
        open(os.path.join(workdir, "dest_hash.txt")).read().strip())

    RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    source = router.register_delivery_identity(
        identity, display_name="NMM Node S (longmsg mesh)",
        stamp_cost=None)

    deadline = time.time() + PATH_DEADLINE
    last_req = 0
    while not RNS.Transport.has_path(dest_hash):
        if time.time() - last_req > PATH_REQUEST_INTERVAL:
            RNS.Transport.request_path(dest_hash)
            last_req = time.time()
        if time.time() > deadline:
            print("[S] TIMEOUT: no path to C", flush=True)
            sys.exit(2)
        time.sleep(0.5)
    hops = RNS.Transport.hops_to(dest_hash)
    print(f"[S] path to C found over modem hops: hops_to(C)={hops} "
          f"(2 proves the path is S -> T -> C; S has NO direct link "
          f"to C)", flush=True)

    dest_identity = RNS.Identity.recall(dest_hash)
    if dest_identity is None:
        print("[S] could not recall C identity", flush=True)
        sys.exit(2)
    dest = RNS.Destination(dest_identity, RNS.Destination.OUT,
                           RNS.Destination.SINGLE, "lxmf", "delivery")

    msg = LXMF.LXMessage(dest, source, content=content,
                         title="nmm-longmsg")
    router.handle_outbound(msg)
    print(f"[S] message handed to router: content {size} B, "
          f"sha256={content_sha}", flush=True)

    pack_deadline = time.time() + 60
    while msg.hash is None and time.time() < pack_deadline:
        time.sleep(0.25)
    sent_info = {"size": size, "content_sha256": content_sha,
                 "hops_to_c": hops,
                 "lxmf_hash": RNS.hexrep(msg.hash, delimit=False)
                 if msg.hash else None,
                 "packed_len": len(msg.packed) if msg.packed else None}
    with open(os.path.join(workdir, "sent_info.json"), "w") as f:
        json.dump(sent_info, f)
    print(f"[S] sent LXMF hash={sent_info['lxmf_hash']} "
          f"packed={sent_info['packed_len']} B", flush=True)

    deliver_deadline = time.time() + DELIVERY_DEADLINE
    last_state = None
    last_attempts = None
    while time.time() < deliver_deadline:
        if msg.state != last_state or \
                msg.delivery_attempts != last_attempts:
            print(f"[S] message state={msg.state} "
                  f"delivery_attempts={msg.delivery_attempts}",
                  flush=True)
            last_state = msg.state
            last_attempts = msg.delivery_attempts
        if msg.state == LXMF.LXMessage.DELIVERED:
            print("[S] delivery confirmed by router state=DELIVERED "
                  "(proof crossed both modem hops back)", flush=True)
            break
        if msg.state == LXMF.LXMessage.FAILED:
            print("[S] router gave up (state=FAILED)", flush=True)
            break
        # Early exit: if C has already validated the content, the
        # end-to-end criterion is met even if the proof is still
        # in flight; record the state as observed and stop.
        if os.path.exists(os.path.join(workdir, "received.json")):
            print("[S] C-side validation file present; ending "
                  "sender watch (delivery state as last logged)",
                  flush=True)
            break
        time.sleep(1)
    result = {"state": msg.state,
              "delivered": msg.state == LXMF.LXMessage.DELIVERED,
              "delivery_attempts": msg.delivery_attempts,
              "hops_to_c": hops}
    with open(os.path.join(workdir, "sender_result.json"), "w") as f:
        json.dump(result, f)
    print(f"[S] sender done: {result}", flush=True)
    time.sleep(3)
    sys.exit(0)


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------

LOG_LINES = []


def log(msg=""):
    line = str(msg)
    print(line, flush=True)
    LOG_LINES.append(line)
    os.makedirs(RESULTS, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def load_stats(work, name):
    path = stats_path(work, name)
    events = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


def hop_summary(tx_events, rx_events):
    tx = [e for e in tx_events if e["event"] == "tx"]
    rx_ok = [e for e in rx_events if e["event"] == "rx_ok"]
    rx_fail = [e for e in rx_events if e["event"] == "rx_fail"]
    distinct = len({e["pkt_sha16"] for e in tx})
    return {
        "frames_tx": len(tx),
        "frames_rx_ok": len(rx_ok),
        "frames_rx_fail": len(rx_fail),
        "airtime_s": round(sum(e["airtime_s"] for e in tx), 1),
        "distinct_packets": distinct,
        "retransmitted_frames": len(tx) - distinct,
        "max_pkt_len": max((e["pkt_len"] for e in tx), default=0),
    }


def run_attempt(size, attempt_no):
    """One full orchestrated end-to-end attempt. Returns a dict."""
    tag = f"size{size}_attempt{attempt_no}"
    work = os.path.join(WORK_ROOT, tag)
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work, exist_ok=True)
    air = air_dirs(work)
    for d in air.values():
        os.makedirs(d, exist_ok=True)

    log(f"--- Attempt: size={size} B, attempt {attempt_no} "
        f"(workdir {tag}) ---")

    py = sys.executable
    script = os.path.abspath(__file__)
    procs, logs = {}, {}

    def spawn(role, *extra):
        logf = open(os.path.join(work, f"{role}.stdout"), "w")
        logs[role] = logf
        procs[role] = subprocess.Popen(
            [py, script, role, work, *extra],
            stdout=logf, stderr=subprocess.STDOUT)

    spawn("transport")
    time.sleep(6)
    spawn("receiver")
    # Wait for C to publish its destination hash before starting S.
    deadline = time.time() + 120
    dest_file = os.path.join(work, "dest_hash.txt")
    while not os.path.exists(dest_file):
        if time.time() > deadline:
            log("FAIL: receiver never published destination hash")
            for p in procs.values():
                p.kill()
            return {"size": size, "attempt": attempt_no,
                    "passed": False, "note": "receiver never started",
                    "wall": 0.0}
        time.sleep(0.25)
    time.sleep(4)
    spawn("sender", str(size))

    t0 = time.time()
    try:
        procs["sender"].wait(timeout=ORCH_SENDER_WAIT)
    except subprocess.TimeoutExpired:
        log("sender timed out (orchestrator limit)")
        procs["sender"].kill()
    for role in ("receiver", "transport"):
        try:
            procs[role].wait(timeout=90)
        except subprocess.TimeoutExpired:
            procs[role].terminate()
            try:
                procs[role].wait(timeout=10)
            except subprocess.TimeoutExpired:
                procs[role].kill()
    wall = time.time() - t0
    for logf in logs.values():
        logf.close()

    for role in ("transport", "receiver", "sender"):
        log(f"--- {role}.stdout (size {size}, attempt {attempt_no}) ---")
        with open(os.path.join(work, f"{role}.stdout")) as f:
            log(f.read().rstrip())
    log("")

    def load_json(name):
        p = os.path.join(work, name)
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
        return None

    received = load_json("received.json")
    sent_info = load_json("sent_info.json")
    sender_result = load_json("sender_result.json")
    t_hops_j = load_json("t_hops.json")
    t_hops = t_hops_j["hops_to_c"] if t_hops_j else None

    stats = {name: load_stats(work, name)
             for name in ("s", "t_facing_s", "t_facing_c", "c")}
    hops = {
        "S->T": hop_summary(stats["s"], stats["t_facing_s"]),
        "T->C": hop_summary(stats["t_facing_c"], stats["c"]),
        "C->T": hop_summary(stats["c"], stats["t_facing_c"]),
        "T->S": hop_summary(stats["t_facing_s"], stats["s"]),
    }
    max_pkt = max(h["max_pkt_len"] for h in hops.values())
    total_airtime = round(sum(h["airtime_s"] for h in hops.values()), 1)
    total_frames = sum(h["frames_tx"] for h in hops.values())
    total_retx = sum(h["retransmitted_frames"] for h in hops.values())

    log(f"--- Per-hop modem statistics (size {size}, "
        f"attempt {attempt_no}) ---")
    for name, h in hops.items():
        log(f"  hop {name}: frames_tx={h['frames_tx']} "
            f"rx_ok={h['frames_rx_ok']} rx_fail={h['frames_rx_fail']} "
            f"distinct_packets={h['distinct_packets']} "
            f"retransmitted_frames={h['retransmitted_frames']} "
            f"airtime={h['airtime_s']} s max_pkt={h['max_pkt_len']} B")
    log(f"  TOTAL: frames_tx={total_frames} "
        f"retransmitted={total_retx} simulated airtime="
        f"{total_airtime} s; wall clock (sender phase): {wall:.0f} s; "
        f"max RNS packet seen: {max_pkt} B")
    log("")

    content_ok = False
    hash_ok = False
    if received is not None and sent_info is not None:
        content_ok = (
            received["content_len"] == size and
            received["content_sha256"] == sent_info["content_sha256"])
        hash_ok = (
            sent_info["lxmf_hash"] is not None and
            received["lxmf_hash"] == sent_info["lxmf_hash"])
        # Byte-level belt-and-braces: compare the dumped content.
        binp = os.path.join(work, "received_content.bin")
        if os.path.exists(binp):
            with open(binp, "rb") as f:
                content_ok = content_ok and \
                    (f.read() == make_content(size))
    passed = content_ok and hash_ok
    attempts = sender_result["delivery_attempts"] if sender_result \
        else None
    s_hops = sender_result["hops_to_c"] if sender_result else None
    log(f"  size={size} attempt={attempt_no}: "
        f"content_ok={content_ok} hash_ok={hash_ok} "
        f"lxmf_delivery_attempts={attempts} "
        f"S hops_to(C)={s_hops} T hops_to(C)={t_hops} "
        f"S DELIVERED={sender_result['delivered'] if sender_result else None} "
        f"packed_len={sent_info['packed_len'] if sent_info else None} B")
    log(f"  ATTEMPT RESULT (size {size}, attempt {attempt_no}): "
        f"{'PASS' if passed else 'FAIL'}")
    log("")
    return {"size": size, "attempt": attempt_no, "passed": passed,
            "content_ok": content_ok, "hash_ok": hash_ok,
            "hops": hops, "total_airtime": total_airtime,
            "total_frames": total_frames, "total_retx": total_retx,
            "max_pkt": max_pkt, "wall": round(wall, 1),
            "lxmf_attempts": attempts,
            "s_delivered": sender_result["delivered"]
            if sender_result else None,
            "packed_len": sent_info["packed_len"] if sent_info
            else None,
            "content_sha256": sent_info["content_sha256"]
            if sent_info else None}


def write_md(size_results, verdict_text):
    lines = []
    lines.append("# Long Messages over the Radio Mesh — Results "
                 "(DIGITAL LAB 3, Part 1)")
    lines.append("")
    lines.append(f"Date (UTC): "
                 f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Question")
    lines.append("DIGITAL LAB 2 delivered a short LXMF message "
                 "(151 B packed) over a two-hop mesh whose every "
                 "link is the nmm_modem over a simulated Watterson "
                 "HF channel at -10 dB per hop. What message sizes "
                 "can that mesh actually carry? This test sends "
                 "LXMF messages with content of 500 B and 1500 B "
                 "over the identical setup and measures the "
                 "envelope honestly.")
    lines.append("")
    lines.append("## Pre-registered criterion")
    lines.append("PASS (per size) = delivery with content bytes AND "
                 "LXMF message hash validated at C (content SHA-256 "
                 "match, LXMF hash match, length match) within 2 "
                 "end-to-end attempts (fresh node trio per attempt). "
                 "OVERALL PASS = both sizes pass. If a size fails "
                 "both attempts, a descent (1000 B, then 750 B) "
                 "finds the largest passing size. Stated in the test "
                 "header before any run.")
    lines.append("")
    lines.append("## Design")
    lines.append("- Identical to DIGITAL LAB 2: nodes S/T/C as "
                 "separate processes whose ONLY interfaces are "
                 "ModemInterface (nmm_modem 16-FSK + RS over the "
                 "Watterson channel, frame_repeats = 3, -10 dB per "
                 "hop, spool-directory 'air'). No TCP/UDP anywhere.")
    lines.append("- Content: exact-length bytes — ASCII header "
                 "`NMM-LONGMSG-<size>B-` + seeded pseudo-random "
                 "bytes (seed fixed per size; reproducible).")
    lines.append("- Larger payloads are handled by LXMF/Reticulum "
                 "natively (link + resource transfer once a message "
                 "outgrows the single-packet path); nothing is "
                 "special-cased.")
    lines.append("")
    lines.append("## Measured envelope")
    lines.append("")
    lines.append("| Content size | Attempt | Result | Wall clock | "
                 "Simulated airtime | Frames TX (all hops) | "
                 "Retrans. frames | LXMF delivery attempts | "
                 "Packed len | Max RNS pkt |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for size in sorted(size_results):
        for r in size_results[size]:
            lines.append(
                f"| {size} B | {r['attempt']} | "
                f"{'PASS' if r['passed'] else 'FAIL'} | "
                f"{r['wall']} s | {r.get('total_airtime', '—')} s | "
                f"{r.get('total_frames', '—')} | "
                f"{r.get('total_retx', '—')} | "
                f"{r.get('lxmf_attempts', '—')} | "
                f"{r.get('packed_len', '—')} B | "
                f"{r.get('max_pkt', '—')} B |")
    lines.append("")
    lines.append(verdict_text)
    lines.append("")
    lines.append("## Honest scope")
    lines.append("Baseband audio + simulated channel models only; "
                 "**no RF was emitted**, nothing was transmitted "
                 "over the air, and no TCP/UDP link exists between "
                 "the nodes. Simulated airtime is the duration the "
                 "frames would occupy on a real ~40 bit/s HF link; "
                 "wall clock is CPU time and is much shorter. The "
                 "remaining physical step is unchanged: real radios "
                 "and licensed spectrum.")
    lines.append("")
    with open(MD_PATH, "w") as f:
        f.write("\n".join(lines))


def orchestrate(sizes):
    os.makedirs(RESULTS, exist_ok=True)
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    if os.path.isdir(WORK_ROOT):
        shutil.rmtree(WORK_ROOT)
    os.makedirs(WORK_ROOT, exist_ok=True)

    log("=== Nature-Mirror Mesh — DIGITAL LAB 3 (Part 1): long "
        "messages over the simulated-radio mesh ===")
    log(f"Pre-registered criterion: PASS per size = content + LXMF "
        f"hash validated at C within {MAX_ATTEMPTS} end-to-end "
        f"attempts; both {SIZES_DEFAULT} must pass for OVERALL PASS; "
        f"descent {DESCENT} if 1500 B fails.")
    log("")

    size_results = {}
    passed_sizes = []

    def try_size(size):
        results = []
        for attempt_no in range(1, MAX_ATTEMPTS + 1):
            r = run_attempt(size, attempt_no)
            results.append(r)
            if r["passed"]:
                break
        size_results[size] = results
        ok = any(r["passed"] for r in results)
        if ok:
            passed_sizes.append(size)
        return ok

    for size in sizes:
        try_size(size)

    # Descent only makes sense if the largest requested size failed.
    largest = max(sizes)
    if largest not in passed_sizes:
        for size in DESCENT:
            if size < largest and size not in size_results:
                log(f"--- Size descent: trying {size} B ---")
                if try_size(size):
                    break

    both = all(s in passed_sizes for s in SIZES_DEFAULT
               if s in sizes)
    envelope = max(passed_sizes) if passed_sizes else None
    if both:
        verdict = (f"## Verdict\n\n**PASS** — both "
                   f"{' and '.join(str(s) + ' B' for s in SIZES_DEFAULT if s in sizes)} "
                   f"delivered with content + hash validated at C "
                   f"within the pre-registered attempt budget. "
                   f"Measured envelope: at least {envelope} B "
                   f"content per message over 2 simulated-radio "
                   f"hops at -10 dB per hop.")
    else:
        verdict = (f"## Verdict\n\n**PARTIAL** — not both target "
                   f"sizes passed. Largest content size delivered "
                   f"with content + hash validated at C: "
                   f"{envelope} B (None passed)" if envelope
                   else "## Verdict\n\n**FAIL** — no tested size "
                        "was delivered within the attempt budget.")
        if envelope:
            verdict = (f"## Verdict\n\n**PARTIAL** — largest "
                       f"content size delivered with content + hash "
                       f"validated at C within the attempt budget: "
                       f"{envelope} B. Failures above are reported, "
                       f"not hidden; the measured envelope is the "
                       f"deliverable.")
    log(verdict.replace("## Verdict\n\n", "VERDICT: "))
    write_md(size_results, verdict)
    log(f"Wrote {LOG_PATH} + {MD_PATH}")
    return 0 if both else 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("transport", "receiver"):
        {"transport": run_transport,
         "receiver": run_receiver}[sys.argv[1]](sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "sender":
        run_sender(sys.argv[2], int(sys.argv[3]))
    else:
        sizes = [int(a) for a in sys.argv[1:] if a.isdigit()] \
            or SIZES_DEFAULT
        sys.exit(orchestrate(sizes))
