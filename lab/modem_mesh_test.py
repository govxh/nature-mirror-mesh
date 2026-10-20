#!/usr/bin/env python3
"""
Nature-Mirror Mesh — DIGITAL LAB 2: MULTI-HOP MESH WHERE EVERY LINK IS
A SIMULATED RADIO LINK (no TCP shortcuts anywhere).

Question
--------
DIGITAL LAB 1 (modem_packet_test.py) proved a full packed LXMF packet
crosses ONE simulated Watterson HF hop via nmm_modem. The phase-2 mesh
test (lxmf_mesh3_test.py) proved Reticulum transport forwarding
S -> T -> C, but over TCP loopback. This test combines them: three
real Reticulum/LXMF node processes whose ONLY interfaces are
ModemInterface (lab/modem_interface.py) — a custom RNS Interface that
modem-encodes every outgoing RNS packet with nmm_modem, passes the
audio through the simulated Watterson channel (tx_chain_test
.apply_channel: two paths 0.5/2.0 ms, powers 0.6/0.4, Rayleigh
envelopes, Gaussian Doppler sigma = 0.7 Hz, AWGN) and delivers it to
the peer as a WAV file in a spool directory; the peer's interface
demodulates it and injects the bytes into its own RNS stack via
Transport.inbound. There is NO other connection of any kind between
the processes: no TCP, no UDP, no shared Reticulum instance.

Topology
--------
    S --modem frames--> T (transport, enable_transport=True)
    T --modem frames--> C
    (plus the reverse directions on the same two hops for announces,
     path traffic and the LXMF delivery proof)
S and C share no interface and no direct link; the only path is
S -> T -> C. Announce and path traffic cross the modem links exactly
like data traffic — nothing is side-channelled. Because one
nmm_modem frame carries up to 4096 bytes and RNS packets here are a
few hundred bytes, every RNS packet fits in exactly ONE modem frame
(frames-per-packet = 1.0; the test logs the maximum RNS packet size
seen to verify the headroom), so no link-layer fragmentation is
required.

PRE-REGISTERED SUCCESS CRITERION (stated here, before any run):
    PASS = C's LXMF layer validates the message sent by S
    (the message is delivered to C's LXMF delivery callback;
    its content equals the token AND its LXMF message hash equals
    the hash of the message S sent), with the delivery having
    traversed BOTH simulated-radio hops at -10 dB per hop, and with
    the LXMF delivery completing within 3 end-to-end attempts
    (LXMF delivery_attempts <= 3; link-level frame retransmissions
    by the stack are allowed, counted and logged).
    S must also report hops_to(C) == 2 and T hops_to(C) == 1,
    proving the transport path.

ATTEMPT HISTORY: run 1 (frame_repeats = 1) FAILED the criterion and
is preserved in results/modem_mesh_test_attempt1.log /
MODEM_MESH_TEST_attempt1.md. Forensics on its frame stats: the
control plane worked (announces crossed both hops; S hops_to(C)=2,
T hops_to(C)=1), S transmitted the data packet once, T received it
and forwarded it once, and that single forward was lost on hop 2 —
per-frame loss at -10 dB for 200-244 B packets measured ~1/3 (the
9/10 figure in DIGITAL LAB 1 was for 147 B packets). LXMF's later
end-to-end attempts never re-crossed (a transport node does not
re-forward a packet it already forwarded; RNS duplicate
suppression), so recovery must happen at the link layer. From run 2
the interface therefore uses frame_repeats = 3: every frame is
transmitted three times through independent channel seeds and the
receiver injects every copy that decodes (RNS dedups the extras).
All repetitions are counted in the stats and in the reported
airtime — this is the "link-level retransmissions allowed, counted
and logged" clause of the criterion above.

HONEST SCOPE: baseband audio + simulated channel models only; no RF
was emitted, nothing was transmitted over the air, and no TCP/UDP
exists between the nodes. Simulated airtime (frame durations at the
modem's ~40 bit/s) is accounted separately from wall-clock time —
the spool delivers frames as fast as the CPU demodulates them, so
wall-clock is much shorter than the simulated airtime.

Usage:  python modem_mesh_test.py            (orchestrated test)
        python modem_mesh_test.py transport <workdir>
        python modem_mesh_test.py receiver  <workdir>
        python modem_mesh_test.py sender    <workdir>
"""

import json
import os
import random
import shutil
import string
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "results")
WORK = os.path.join(BASE, "modem_mesh_work")
TOKEN_FILE = os.path.join(WORK, "token.txt")
DEST_FILE = os.path.join(WORK, "dest_hash.txt")
RECEIVED_FILE = os.path.join(WORK, "received.json")
SENT_INFO_FILE = os.path.join(WORK, "sent_info.json")
SENDER_RESULT_FILE = os.path.join(WORK, "sender_result.json")

SNR_DB = -10.0
ANNOUNCE_INTERVAL = 15          # seconds between C announces
PATH_REQUEST_INTERVAL = 15      # seconds between S path requests

# Directed "air" spool directories (frames written by the first node
# are demodulated by the second).
AIR = {
    "st": os.path.join(WORK, "air", "s_to_t"),
    "ts": os.path.join(WORK, "air", "t_to_s"),
    "tc": os.path.join(WORK, "air", "t_to_c"),
    "ct": os.path.join(WORK, "air", "c_to_t"),
}
SEEDS = {"st": 3301, "ts": 3302, "tc": 3303, "ct": 3304}


def stats_path(name):
    return os.path.join(WORK, f"stats_{name}.jsonl")


def write_config(configdir, role):
    os.makedirs(os.path.join(configdir, "interfaces"), exist_ok=True)
    shutil.copy(os.path.join(BASE, "modem_interface.py"),
                os.path.join(configdir, "interfaces",
                             "ModemInterface.py"))

    def iface_section(name, tx_key, rx_key, stats_name):
        return f"""  [[{name}]]
    type = ModemInterface
    enabled = True
    tx_dir = {AIR[tx_key]}
    rx_dir = {AIR[rx_key]}
    stats_path = {stats_path(stats_name)}
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
  loglevel = 4

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
    write_config(configdir, "transport")
    RNS.Reticulum(configdir=configdir)
    print(f"[T] transport node up (modem interfaces only), transport "
          f"identity {RNS.hexrep(RNS.Transport.identity.hash, delimit=False)}",
          flush=True)

    deadline = time.time() + 1560
    reported = False
    while time.time() < deadline:
        if os.path.exists(DEST_FILE) and not reported:
            dest_hash = bytes.fromhex(open(DEST_FILE).read().strip())
            if RNS.Transport.has_path(dest_hash):
                print(f"[T] learned path to C over modem hop: "
                      f"hops_to(C)={RNS.Transport.hops_to(dest_hash)} "
                      f"(1 = C is one modem hop from T)", flush=True)
                with open(os.path.join(workdir, "t_hops.json"), "w") as f:
                    json.dump({"hops_to_c":
                               RNS.Transport.hops_to(dest_hash)}, f)
                reported = True
        if os.path.exists(RECEIVED_FILE):
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
    write_config(configdir, "receiver")
    storage = os.path.join(workdir, "storage_c")
    os.makedirs(storage, exist_ok=True)

    RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    delivery = router.register_delivery_identity(
        identity, display_name="NMM Node C (modem mesh)", stamp_cost=None)
    router.register_delivery_callback(
        lambda m: on_message(m, workdir))

    with open(DEST_FILE, "w") as f:
        f.write(RNS.hexrep(delivery.hash, delimit=False))
    print(f"[C] delivery destination: "
          f"{RNS.hexrep(delivery.hash, delimit=False)}", flush=True)

    deadline = time.time() + 1500
    while time.time() < deadline and not os.path.exists(RECEIVED_FILE):
        router.announce(delivery.hash)
        print("[C] announced over modem hop (will propagate "
              "C -> T -> S)", flush=True)
        time.sleep(ANNOUNCE_INTERVAL)

    if os.path.exists(RECEIVED_FILE):
        print("[C] message received and written to file", flush=True)
        time.sleep(3)
        sys.exit(0)
    print("[C] TIMEOUT waiting for message", flush=True)
    sys.exit(2)


def on_message(message, workdir):
    import RNS
    try:
        content = message.content_as_string()
    except Exception:
        content = message.content.decode("utf-8", "replace")
    msg_hash = RNS.hexrep(message.hash, delimit=False)
    print(f"[C] DECRYPTED MESSAGE RECEIVED (via 2 modem hops): {content}",
          flush=True)
    print(f"[C] LXMF message hash: {msg_hash}", flush=True)
    with open(RECEIVED_FILE, "w") as f:
        json.dump({"content": content, "lxmf_hash": msg_hash,
                   "source_hash": RNS.hexrep(message.source_hash,
                                             delimit=False)}, f)


def run_sender(workdir):
    import RNS
    import LXMF

    configdir = os.path.join(workdir, "node_s")
    write_config(configdir, "sender")
    storage = os.path.join(workdir, "storage_s")
    os.makedirs(storage, exist_ok=True)

    token = open(TOKEN_FILE).read().strip()
    dest_hash = bytes.fromhex(open(DEST_FILE).read().strip())

    RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    source = router.register_delivery_identity(
        identity, display_name="NMM Node S (modem mesh)", stamp_cost=None)

    deadline = time.time() + 600
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

    msg = LXMF.LXMessage(dest, source, content=token,
                         title="nmm-modem-mesh")
    router.handle_outbound(msg)
    print(f"[S] message handed to router, token={token}", flush=True)

    # The router packs the message in its outbound thread; wait for the
    # pack so the sent hash / packed size can be recorded as evidence.
    pack_deadline = time.time() + 30
    while msg.hash is None and time.time() < pack_deadline:
        time.sleep(0.25)
    sent_info = {"token": token, "hops_to_c": hops,
                 "lxmf_hash": RNS.hexrep(msg.hash, delimit=False)
                 if msg.hash else None,
                 "packed_len": len(msg.packed) if msg.packed else None}
    with open(SENT_INFO_FILE, "w") as f:
        json.dump(sent_info, f)
    print(f"[S] sent LXMF hash={sent_info['lxmf_hash']} "
          f"packed={sent_info['packed_len']} B", flush=True)

    deliver_deadline = time.time() + 900
    last_state = None
    while time.time() < deliver_deadline:
        if msg.state != last_state:
            print(f"[S] message state={msg.state} "
                  f"delivery_attempts={msg.delivery_attempts}",
                  flush=True)
            last_state = msg.state
        if msg.state == LXMF.LXMessage.DELIVERED:
            print("[S] delivery confirmed by router state=DELIVERED "
                  "(proof crossed both modem hops back)", flush=True)
            break
        if msg.state == LXMF.LXMessage.FAILED:
            print("[S] router gave up (state=FAILED)", flush=True)
            break
        time.sleep(1)
    result = {"state": msg.state,
              "delivered": msg.state == LXMF.LXMessage.DELIVERED,
              "delivery_attempts": msg.delivery_attempts,
              "hops_to_c": hops}
    with open(SENDER_RESULT_FILE, "w") as f:
        json.dump(result, f)
    print(f"[S] sender done: {result}", flush=True)
    time.sleep(3)
    sys.exit(0)


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------

LOG_LINES = []


def log(msg=""):
    print(msg, flush=True)
    LOG_LINES.append(str(msg))


def load_stats(name):
    path = stats_path(name)
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


def orchestrate():
    os.makedirs(RESULTS, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK, exist_ok=True)
    for d in AIR.values():
        os.makedirs(d, exist_ok=True)

    rng = random.Random()
    suffix = "".join(rng.choice(string.ascii_uppercase + string.digits)
                     for _ in range(12))
    token = f"NMM-MODEMMESH-{suffix}"
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

    log("=== Nature-Mirror Mesh — DIGITAL LAB 2: multi-hop mesh, "
        "every link a simulated radio link ===")
    log(f"Token: {token}")
    log(f"Pre-registered criterion: PASS = C's LXMF layer validates "
        f"the message (content == token AND LXMF hash == sent hash) "
        f"after traversing BOTH modem hops at {SNR_DB:+.0f} dB per "
        f"hop, within 3 end-to-end (LXMF) attempts; S hops_to(C)==2 "
        f"and T hops_to(C)==1.")
    log("")

    py = sys.executable
    procs, logs = {}, {}
    for role in ("transport", "receiver", "sender"):
        if role == "sender":
            deadline = time.time() + 60
            while not os.path.exists(DEST_FILE):
                if time.time() > deadline:
                    log("FAIL: receiver never published destination hash")
                    for p in procs.values():
                        p.kill()
                    _write_outputs(token, None, None, None, False,
                                   "receiver never started")
                    return 1
                time.sleep(0.25)
        logf = open(os.path.join(WORK, f"{role}.stdout"), "w")
        logs[role] = logf
        procs[role] = subprocess.Popen(
            [py, os.path.abspath(__file__), role, WORK],
            stdout=logf, stderr=subprocess.STDOUT)
        if role == "transport":
            time.sleep(6)
        elif role == "receiver":
            time.sleep(10)

    t0 = time.time()
    try:
        procs["sender"].wait(timeout=1560)
    except subprocess.TimeoutExpired:
        log("sender timed out (orchestrator limit)")
        procs["sender"].kill()
    for role in ("receiver", "transport"):
        try:
            procs[role].wait(timeout=60)
        except subprocess.TimeoutExpired:
            procs[role].terminate()
    wall = time.time() - t0
    for logf in logs.values():
        logf.close()

    for role in ("transport", "receiver", "sender"):
        log(f"--- {role}.stdout ---")
        with open(os.path.join(WORK, f"{role}.stdout")) as f:
            log(f.read().rstrip())
    log("")

    # --- Evidence ------------------------------------------------------
    received = None
    if os.path.exists(RECEIVED_FILE):
        with open(RECEIVED_FILE) as f:
            received = json.load(f)
    sent_info = None
    if os.path.exists(SENT_INFO_FILE):
        with open(SENT_INFO_FILE) as f:
            sent_info = json.load(f)
    sender_result = None
    if os.path.exists(SENDER_RESULT_FILE):
        with open(SENDER_RESULT_FILE) as f:
            sender_result = json.load(f)
    t_hops = None
    if os.path.exists(os.path.join(WORK, "t_hops.json")):
        with open(os.path.join(WORK, "t_hops.json")) as f:
            t_hops = json.load(f)["hops_to_c"]

    stats = {name: load_stats(name)
             for name in ("s", "t_facing_s", "t_facing_c", "c")}
    hops = {
        "S->T": hop_summary(stats["s"], stats["t_facing_s"]),
        "T->C": hop_summary(stats["t_facing_c"], stats["c"]),
        "C->T": hop_summary(stats["c"], stats["t_facing_c"]),
        "T->S": hop_summary(stats["t_facing_s"], stats["s"]),
    }
    max_pkt = max(h["max_pkt_len"] for h in hops.values())
    total_airtime = round(sum(h["airtime_s"] for h in hops.values()), 1)

    log("--- Per-hop modem statistics ---")
    for name, h in hops.items():
        log(f"  hop {name}: frames_tx={h['frames_tx']} "
            f"rx_ok={h['frames_rx_ok']} rx_fail={h['frames_rx_fail']} "
            f"distinct_packets={h['distinct_packets']} "
            f"retransmitted_frames={h['retransmitted_frames']} "
            f"airtime={h['airtime_s']} s max_pkt={h['max_pkt_len']} B")
    log(f"  TOTAL simulated airtime: {total_airtime} s; wall clock "
        f"(sender phase): {wall:.0f} s; max RNS packet seen: "
        f"{max_pkt} B (modem frame capacity 4096 B -> "
        f"frames-per-packet = 1)")
    log("")

    content_ok = received is not None and \
        received["content"] == token
    hash_ok = received is not None and sent_info is not None and \
        sent_info["lxmf_hash"] is not None and \
        received["lxmf_hash"] == sent_info["lxmf_hash"]
    attempts = sender_result["delivery_attempts"] if sender_result \
        else None
    s_hops = sender_result["hops_to_c"] if sender_result else None
    attempts_ok = attempts is not None and attempts <= 3
    hops_ok = (s_hops == 2 and t_hops == 1)
    both_hops = hops["S->T"]["frames_tx"] > 0 and \
        hops["S->T"]["frames_rx_ok"] > 0 and \
        hops["T->C"]["frames_tx"] > 0 and \
        hops["T->C"]["frames_rx_ok"] > 0

    log(f"Sent token:     {token}")
    log(f"Received token: {received['content'] if received else None}")
    log(f"Sent LXMF hash:     {sent_info['lxmf_hash'] if sent_info else None}")
    log(f"Received LXMF hash: {received['lxmf_hash'] if received else None}")
    log(f"LXMF delivery_attempts at S: {attempts} (criterion: <= 3)")
    log(f"S hops_to(C)={s_hops}, T hops_to(C)={t_hops}")
    log(f"S router DELIVERED state reached: "
        f"{sender_result['delivered'] if sender_result else None}")
    passed = content_ok and hash_ok and attempts_ok and hops_ok \
        and both_hops
    log(f"RESULT: {'PASS' if passed else 'FAIL'} — "
        f"content_ok={content_ok} hash_ok={hash_ok} "
        f"attempts_ok={attempts_ok} hops_ok={hops_ok} "
        f"both_hops_carried={both_hops}")

    _write_outputs(token, hops, {
        "received": received, "sent_info": sent_info,
        "sender_result": sender_result, "t_hops": t_hops,
        "total_airtime": total_airtime, "wall": wall,
        "max_pkt": max_pkt}, passed, None)
    return 0 if passed else 1


def _write_outputs(token, hops, ev, verdict, note):
    with open(os.path.join(RESULTS, "modem_mesh_test.log"), "w") as f:
        f.write("\n".join(LOG_LINES) + "\n")
    lines = []
    lines.append("# Multi-Hop Mesh over Modem Links — Results "
                 "(DIGITAL LAB 2)")
    lines.append("")
    lines.append(f"Date (UTC): "
                 f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Question")
    lines.append("DIGITAL LAB 1 proved a full LXMF packet crosses ONE "
                 "simulated Watterson hop via nmm_modem; the phase-2 "
                 "mesh test proved Reticulum transport forwarding "
                 "S -> T -> C over TCP. Can the two be combined — a "
                 "three-node mesh where EVERY link is the modem over "
                 "a simulated HF channel, with no TCP anywhere?")
    lines.append("")
    lines.append("## Implementation tier achieved")
    lines.append("**Tier (1) — custom Reticulum Interface.** "
                 "lab/modem_interface.py subclasses "
                 "RNS.Interfaces.Interface.Interface and is loaded by "
                 "each node through Reticulum's external-interface "
                 "mechanism (config `type = ModemInterface`, module "
                 "in <configdir>/interfaces/). Outgoing RNS packets "
                 "are modem-encoded, passed through the Watterson "
                 "channel and spooled as WAV frames; the peer "
                 "interface demodulates them into Transport.inbound. "
                 "Announce, path and proof traffic cross the modem "
                 "links exactly like data. No fallback to an "
                 "application-level relay was needed.")
    lines.append("")
    lines.append("## Pre-registered criterion")
    lines.append("PASS = C's LXMF layer validates the message "
                 "(content == token AND LXMF hash == sent hash) "
                 "after traversing both modem hops at -10 dB per "
                 "hop, within 3 end-to-end (LXMF) attempts; "
                 "S hops_to(C)==2 and T hops_to(C)==1. Stated in the "
                 "test header before any run.")
    lines.append("")
    lines.append("## Design")
    lines.append("- Nodes: S (sender), T (transport, "
                 "enable_transport=True), C (receiver) — separate "
                 "processes, separate Reticulum config dirs, the "
                 "ONLY interfaces are ModemInterface instances.")
    lines.append("- Medium: one spool directory of WAV frames per "
                 "directed hop (S->T, T->S, T->C, C->T). The "
                 "transmitting interface applies the channel "
                 "(tx_chain_test.apply_channel: two paths "
                 "0.5/2.0 ms, powers 0.6/0.4, Rayleigh envelopes, "
                 "Doppler sigma 0.7 Hz, AWGN) at -10 dB with a "
                 "per-link, per-frame seed; the file on disk is "
                 "the post-channel audio.")
    lines.append("- Fragmentation: none needed — see stats (max RNS "
                 "packet vs 4096 B modem frame capacity; "
                 "frames-per-packet = 1).")
    lines.append("- Link-level repetition: every frame is "
                 "transmitted 3x (frame_repeats = 3), each copy "
                 "through an independent channel seed; the receiver "
                 "injects every copy that decodes and RNS dedups "
                 "the extras. Added after run 1, where the data "
                 "packet's single hop-2 forward was lost (per-frame "
                 "loss ~1/3 at 200-244 B, -10 dB) and LXMF "
                 "end-to-end retransmission could not recover it. "
                 "The 'Retransmitted frames' column counts these "
                 "deliberate repetitions plus any stack-level "
                 "retransmissions; all are included in airtime.")
    lines.append("")
    if hops is not None:
        lines.append("## Per-hop statistics")
        lines.append("")
        lines.append("| Hop | Frames TX | RX ok | RX fail (lost) | "
                     "Distinct packets | Retransmitted frames | "
                     "Simulated airtime | Max packet |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for name in ("S->T", "T->C", "C->T", "T->S"):
            h = hops[name]
            lines.append(f"| {name} | {h['frames_tx']} | "
                         f"{h['frames_rx_ok']} | "
                         f"{h['frames_rx_fail']} | "
                         f"{h['distinct_packets']} | "
                         f"{h['retransmitted_frames']} | "
                         f"{h['airtime_s']} s | {h['max_pkt_len']} B |")
        lines.append("")
        lines.append(f"Total simulated airtime: "
                     f"{ev['total_airtime']} s; wall clock (sender "
                     f"phase): {ev['wall']:.0f} s; maximum RNS packet "
                     f"seen on any interface: {ev['max_pkt']} B.")
        lines.append("")
        lines.append("## Evidence at C")
        lines.append("")
        r = ev["received"]
        s = ev["sent_info"]
        sr = ev["sender_result"]
        lines.append(f"- Token sent by S: `{token}`")
        lines.append(f"- Token received at C: "
                     f"`{r['content'] if r else None}`")
        lines.append(f"- LXMF hash at S: "
                     f"`{s['lxmf_hash'] if s else None}`")
        lines.append(f"- LXMF hash at C: "
                     f"`{r['lxmf_hash'] if r else None}`")
        lines.append(f"- LXMF packed size: "
                     f"{s['packed_len'] if s else None} B")
        lines.append(f"- S hops_to(C): "
                     f"{sr['hops_to_c'] if sr else None}; "
                     f"T hops_to(C): {ev['t_hops']}")
        lines.append(f"- LXMF delivery_attempts at S: "
                     f"{sr['delivery_attempts'] if sr else None} "
                     f"(criterion <= 3)")
        lines.append(f"- S router reached DELIVERED state: "
                     f"{sr['delivered'] if sr else None} "
                     f"(the LXMF proof crossed both hops back)")
        lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{'PASS' if verdict else 'FAIL'}** — against the "
                 f"pre-registered criterion above."
                 + (f" Note: {note}" if note else ""))
    lines.append("")
    lines.append("## Honest scope")
    lines.append("Baseband audio + simulated channel models only; "
                 "**no RF was emitted**, nothing was transmitted "
                 "over the air, and no TCP/UDP link exists between "
                 "the nodes — the spool files carry post-channel "
                 "audio, nothing else. Simulated airtime is the "
                 "duration the frames would occupy on a real "
                 "~40 bit/s HF link; the lab machines exchange them "
                 "at CPU speed, so wall-clock time is much shorter. "
                 "The remaining physical step is unchanged: real "
                 "radios and licensed spectrum.")
    lines.append("")
    with open(os.path.join(RESULTS, "MODEM_MESH_TEST.md"), "w") as f:
        f.write("\n".join(lines))
    log("Wrote lab/results/modem_mesh_test.log + MODEM_MESH_TEST.md")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("transport", "receiver",
                                             "sender"):
        {"transport": run_transport, "receiver": run_receiver,
         "sender": run_sender}[sys.argv[1]](sys.argv[2])
    else:
        sys.exit(orchestrate())
