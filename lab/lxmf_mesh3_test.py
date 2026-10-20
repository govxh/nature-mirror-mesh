#!/usr/bin/env python3
"""
Nature-Mirror Mesh — Lab Test 2 (Phase 2): THREE-node LXMF mesh with
transport forwarding through a middle node.

Topology (TCP loopback only — this sandbox blocks all UDP sends with EPERM):

        Node S (sender)                Node C (receiver)
        TCPClient -> 127.0.0.1:51722   TCPClient -> 127.0.0.1:51721
                    \                  /
                     \                /
                      Node T (TRANSPORT, enable_transport = True)
                      TCPServer on 51721 (faces C) + TCPServer on 51722 (faces S)

IMPORTANT TOPOLOGY FACT: Node S and Node C share NO interface and have NO
direct connection of any kind. S's only interface points at T; C's only
interface points at T. The only possible path S -> C is S -> T -> C, with T
acting as a Reticulum transport (store-and-forward / packet relay) node.
Proof in the logs: S reports RNS.Transport.hops_to(C) == 2, T reports
hops_to(C) == 1, and C prints the decrypted token that only S knew.

Flow mirrors the phase-1 pattern (separate processes, separate config dirs):
T starts first; C registers an LXMF delivery identity and announces (its
announce propagates C -> T -> S via transport); S requests the path, recalls
C's identity, and sends an LXMF message carrying a fresh unique token; C's
delivery callback prints the decrypted content. Exit 0 only on exact token
match at C.

Usage (orchestrated mode, normal):
    python lxmf_mesh3_test.py
Worker modes (used internally):
    python lxmf_mesh3_test.py transport <workdir>
    python lxmf_mesh3_test.py receiver  <workdir>
    python lxmf_mesh3_test.py sender    <workdir>
"""

import os
import sys
import time
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "results")
WORK = os.path.join(BASE, "lxmf_mesh3_work")
TOKEN_FILE = os.path.join(WORK, "token.txt")
DEST_FILE = os.path.join(WORK, "dest_hash.txt")
RECEIVED_FILE = os.path.join(WORK, "received.txt")

PORT_T_FOR_C = 51721   # T listens here; C connects here
PORT_T_FOR_S = 51722   # T listens here; S connects here


def write_config(configdir, role):
    os.makedirs(configdir, exist_ok=True)
    if role == "transport":
        iface = f"""  [[T server facing C]]
    type = TCPServerInterface
    enabled = True
    listen_ip = 127.0.0.1
    listen_port = {PORT_T_FOR_C}

  [[T server facing S]]
    type = TCPServerInterface
    enabled = True
    listen_ip = 127.0.0.1
    listen_port = {PORT_T_FOR_S}"""
        transport = "True"
    elif role == "receiver":  # C connects ONLY to T
        iface = f"""  [[Link to T only]]
    type = TCPClientInterface
    enabled = True
    target_host = 127.0.0.1
    target_port = {PORT_T_FOR_C}"""
        transport = "False"
    else:  # sender S connects ONLY to T — no interface to C exists
        iface = f"""  [[Link to T only]]
    type = TCPClientInterface
    enabled = True
    target_host = 127.0.0.1
    target_port = {PORT_T_FOR_S}"""
        transport = "False"
    cfg = f"""[reticulum]
  enable_transport = {transport}
  share_instance = False
  panic_on_interface_error = False

[logging]
  loglevel = 4

[interfaces]
{iface}
"""
    with open(os.path.join(configdir, "config"), "w") as f:
        f.write(cfg)


def run_transport(workdir):
    import RNS

    configdir = os.path.join(workdir, "node_t")
    write_config(configdir, "transport")
    reticulum = RNS.Reticulum(configdir=configdir)
    print(f"[T] transport node up, transport identity {RNS.hexrep(RNS.Transport.identity.hash, delimit=False)}", flush=True)

    deadline = time.time() + 170
    reported = False
    while time.time() < deadline:
        if os.path.exists(DEST_FILE) and not reported:
            dest_hash = bytes.fromhex(open(DEST_FILE).read().strip())
            if RNS.Transport.has_path(dest_hash):
                print(f"[T] learned path to C: hops_to(C)={RNS.Transport.hops_to(dest_hash)} "
                      f"(1 = C is one hop from T, via T's own server interface)", flush=True)
                reported = True
        if os.path.exists(RECEIVED_FILE):
            print("[T] relay job done (C received the message); T forwarded traffic between S and C", flush=True)
            time.sleep(2)
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

    reticulum = RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    delivery = router.register_delivery_identity(identity, display_name="NMM Node C", stamp_cost=None)
    router.register_delivery_callback(on_message)

    with open(DEST_FILE, "w") as f:
        f.write(RNS.hexrep(delivery.hash, delimit=False))
    print(f"[C] delivery destination: {RNS.hexrep(delivery.hash, delimit=False)}", flush=True)

    deadline = time.time() + 150
    while time.time() < deadline and not os.path.exists(RECEIVED_FILE):
        router.announce(delivery.hash)
        print("[C] announced (will propagate C -> T -> S), waiting...", flush=True)
        time.sleep(4)

    if os.path.exists(RECEIVED_FILE):
        print("[C] message received and written to file", flush=True)
        time.sleep(2)
        sys.exit(0)
    print("[C] TIMEOUT waiting for message", flush=True)
    sys.exit(2)


def on_message(message):
    try:
        content = message.content_as_string()
    except Exception:
        content = message.content.decode("utf-8", "replace")
    print(f"[C] DECRYPTED MESSAGE RECEIVED: {content}", flush=True)
    with open(RECEIVED_FILE, "w") as f:
        f.write(content)


def run_sender(workdir):
    import RNS
    import LXMF

    configdir = os.path.join(workdir, "node_s")
    write_config(configdir, "sender")
    storage = os.path.join(workdir, "storage_s")
    os.makedirs(storage, exist_ok=True)

    token = open(TOKEN_FILE).read().strip()
    dest_hash = bytes.fromhex(open(DEST_FILE).read().strip())

    reticulum = RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    source = router.register_delivery_identity(identity, display_name="NMM Node S", stamp_cost=None)

    deadline = time.time() + 120
    last_req = 0
    while not RNS.Transport.has_path(dest_hash):
        # Re-request at most every 5 s: hammering request_path() can keep
        # resetting Reticulum's path-request state and delay the response.
        if time.time() - last_req > 5:
            RNS.Transport.request_path(dest_hash)
            last_req = time.time()
        if time.time() > deadline:
            print("[S] TIMEOUT: no path to C", flush=True)
            sys.exit(2)
        time.sleep(0.5)
    hops = RNS.Transport.hops_to(dest_hash)
    print(f"[S] path to C found: hops_to(C)={hops} (2 proves the path is S -> T -> C; "
          f"S has NO direct interface to C)", flush=True)

    dest_identity = RNS.Identity.recall(dest_hash)
    if dest_identity is None:
        print("[S] could not recall C identity", flush=True)
        sys.exit(2)
    dest = RNS.Destination(dest_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")

    msg = LXMF.LXMessage(dest, source, content=token, title="nmm-mesh3")
    router.handle_outbound(msg)
    print(f"[S] message sent (state={msg.state}), token={token}", flush=True)

    deliver_deadline = time.time() + 60
    while time.time() < deliver_deadline:
        if msg.state == LXMF.LXMessage.DELIVERED:
            print("[S] delivery confirmed by router state=DELIVERED (end-to-end, via T)", flush=True)
            break
        time.sleep(0.5)
    print(f"[S] sender done, final message state={msg.state}", flush=True)
    time.sleep(2)
    sys.exit(0)


def orchestrate():
    import shutil
    os.makedirs(RESULTS, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK, exist_ok=True)

    token = "NMM-MESH3-" + time.strftime("%Y%m%d-%H%M%S")
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    print(f"=== LXMF 3-node mesh test (S -> T -> C, transport forwarding) ===\nToken: {token}", flush=True)

    py = sys.executable
    procs = {}
    logs = {}
    for role in ("transport", "receiver", "sender"):
        if role == "sender":
            # Wait for receiver to publish its destination hash first.
            deadline = time.time() + 30
            while not os.path.exists(DEST_FILE):
                if time.time() > deadline:
                    print("FAIL: receiver never published destination hash")
                    for p in procs.values():
                        p.kill()
                    return 1
                time.sleep(0.25)
        logf = open(os.path.join(WORK, f"{role}.stdout"), "w")
        logs[role] = logf
        procs[role] = subprocess.Popen([py, os.path.abspath(__file__), role, WORK],
                                       stdout=logf, stderr=subprocess.STDOUT)
        if role == "transport":
            time.sleep(5)  # let T bind both server interfaces
        elif role == "receiver":
            time.sleep(8)  # let C's first announces reach and settle at T before S asks

    try:
        procs["sender"].wait(timeout=180)
    except subprocess.TimeoutExpired:
        print("sender timed out")
    for role in ("receiver", "transport"):
        try:
            procs[role].wait(timeout=25)
        except subprocess.TimeoutExpired:
            procs[role].terminate()
    for logf in logs.values():
        logf.close()

    for role in ("transport", "receiver", "sender"):
        print(f"--- {role}.stdout ---")
        with open(os.path.join(WORK, f"{role}.stdout")) as f:
            print(f.read())

    if os.path.exists(RECEIVED_FILE):
        received = open(RECEIVED_FILE).read()
        print(f"Sent token:     {token}")
        print(f"Received token: {received}")
        if received == token:
            print("RESULT: PASS — LXMF message delivered S -> T -> C via transport node; "
                  "S and C share no interface (see script header)")
            return 0
        print("RESULT: FAIL — content mismatch")
        return 1
    print("RESULT: FAIL — no message received at C")
    return 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] in ("transport", "receiver", "sender"):
        {"transport": run_transport, "receiver": run_receiver, "sender": run_sender}[sys.argv[1]](sys.argv[2])
    else:
        sys.exit(orchestrate())
