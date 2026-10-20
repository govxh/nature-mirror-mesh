#!/usr/bin/env python3
"""
Nature-Mirror Mesh — Lab Test 1: LXMF two-node end-to-end encrypted delivery.

Two separate Reticulum instances (two OS processes, two separate config dirs)
connected ONLY over a local UDP interface pair on 127.0.0.1 (no radio, no
internet). Node A (receiver) registers an LXMF delivery identity and
announces it. Node B (sender) discovers A via the announce, requests the
path, recalls A's identity, and sends an opportunistic/direct LXMF message
containing a unique runtime token. A decrypts it in its delivery callback.

Exit code 0 only if A's received content exactly matches B's sent token.

Usage (orchestrated mode, normal):
    python lxmf_two_node_test.py
Worker modes (used internally):
    python lxmf_two_node_test.py receiver <workdir>
    python lxmf_two_node_test.py sender   <workdir>
"""

import os
import sys
import time
import json
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE, "results")
WORK = os.path.join(BASE, "lxmf_work")
TOKEN_FILE = os.path.join(WORK, "token.txt")
DEST_FILE = os.path.join(WORK, "dest_hash.txt")
RECEIVED_FILE = os.path.join(WORK, "received.txt")
SENT_FILE = os.path.join(WORK, "sent.txt")

PORT_A_LISTEN = 51711   # A listens here, B forwards here
PORT_B_LISTEN = 51712   # B listens here, A forwards here


def write_config(configdir, role):
    """Local link over TCP on 127.0.0.1 only.

    Note: this sandbox blocks ALL UDP sends (Errno 1 / EPERM), even on
    loopback — verified with a plain Python socket test. TCP loopback works,
    so A runs a TCPServerInterface and B connects with TCPClientInterface.
    """
    os.makedirs(configdir, exist_ok=True)
    if role == "server":
        iface = f"""  [[Local TCP Link]]
    type = TCPServerInterface
    enabled = True
    listen_ip = 127.0.0.1
    listen_port = {PORT_A_LISTEN}"""
    else:
        iface = f"""  [[Local TCP Link]]
    type = TCPClientInterface
    enabled = True
    target_host = 127.0.0.1
    target_port = {PORT_A_LISTEN}"""
    cfg = f"""[reticulum]
  enable_transport = False
  share_instance = False
  panic_on_interface_error = False

[logging]
  loglevel = 4

[interfaces]
{iface}
"""
    with open(os.path.join(configdir, "config"), "w") as f:
        f.write(cfg)


def run_receiver(workdir):
    import RNS
    import LXMF

    configdir = os.path.join(workdir, "node_a")
    write_config(configdir, "server")
    storage = os.path.join(workdir, "storage_a")
    os.makedirs(storage, exist_ok=True)

    reticulum = RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    delivery = router.register_delivery_identity(identity, display_name="NMM Node A", stamp_cost=None)
    router.register_delivery_callback(on_message)

    with open(DEST_FILE, "w") as f:
        f.write(RNS.hexrep(delivery.hash, delimit=False))
    print(f"[A] delivery destination: {RNS.hexrep(delivery.hash, delimit=False)}", flush=True)

    # Announce repeatedly so B can learn the path even if it starts late.
    deadline = time.time() + 90
    while time.time() < deadline and not os.path.exists(RECEIVED_FILE):
        router.announce(delivery.hash)
        print("[A] announced, waiting for message...", flush=True)
        time.sleep(5)

    if os.path.exists(RECEIVED_FILE):
        print("[A] message received and written to file", flush=True)
        time.sleep(2)
        sys.exit(0)
    print("[A] TIMEOUT waiting for message", flush=True)
    sys.exit(2)


def on_message(message):
    try:
        content = message.content_as_string()
    except Exception:
        content = message.content.decode("utf-8", "replace")
    print(f"[A] DECRYPTED MESSAGE RECEIVED: {content}", flush=True)
    with open(RECEIVED_FILE, "w") as f:
        f.write(content)


def run_sender(workdir):
    import RNS
    import LXMF

    configdir = os.path.join(workdir, "node_b")
    write_config(configdir, "client")
    storage = os.path.join(workdir, "storage_b")
    os.makedirs(storage, exist_ok=True)

    with open(TOKEN_FILE) as f:
        token = f.read().strip()
    with open(DEST_FILE) as f:
        dest_hash = bytes.fromhex(f.read().strip())

    reticulum = RNS.Reticulum(configdir=configdir)
    identity = RNS.Identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=storage)
    source = router.register_delivery_identity(identity, display_name="NMM Node B", stamp_cost=None)

    # Wait for A's announce / path.
    deadline = time.time() + 60
    while not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)
        if time.time() > deadline:
            print("[B] TIMEOUT: no path to A", flush=True)
            sys.exit(2)
        time.sleep(0.5)
    print("[B] path to A found", flush=True)

    dest_identity = RNS.Identity.recall(dest_hash)
    if dest_identity is None:
        print("[B] could not recall A identity", flush=True)
        sys.exit(2)
    dest = RNS.Destination(dest_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")

    msg = LXMF.LXMessage(dest, source, content=token, title="nmm-test")
    router.handle_outbound(msg)
    print(f"[B] message sent (state={msg.state}), token={token}", flush=True)

    # Give the router time to actually deliver (opportunistic/direct).
    deliver_deadline = time.time() + 45
    while time.time() < deliver_deadline:
        if msg.state == LXMF.LXMessage.DELIVERED:
            print("[B] delivery confirmed by router state=DELIVERED", flush=True)
            break
        time.sleep(0.5)
    with open(SENT_FILE, "w") as f:
        f.write(token)
    print(f"[B] sender done, final message state={msg.state}", flush=True)
    time.sleep(2)
    sys.exit(0)


def orchestrate():
    import shutil
    os.makedirs(RESULTS, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK, exist_ok=True)

    token = "NMM-TEST-" + time.strftime("%Y%m%d-%H%M%S")
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    print(f"=== LXMF two-node test ===\nToken: {token}", flush=True)

    py = sys.executable
    recv_log = open(os.path.join(WORK, "receiver.stdout"), "w")
    recv = subprocess.Popen([py, os.path.abspath(__file__), "receiver", WORK],
                            stdout=recv_log, stderr=subprocess.STDOUT)

    # Wait for receiver to publish its destination hash.
    deadline = time.time() + 30
    while not os.path.exists(DEST_FILE):
        if time.time() > deadline:
            print("FAIL: receiver never published destination hash")
            recv.kill()
            return 1
        time.sleep(0.25)

    send_log = open(os.path.join(WORK, "sender.stdout"), "w")
    send = subprocess.Popen([py, os.path.abspath(__file__), "sender", WORK],
                            stdout=send_log, stderr=subprocess.STDOUT)
    send.wait(timeout=150)
    send_log.close()

    # Receiver should exit on its own after receipt; give it a moment.
    try:
        recv.wait(timeout=20)
    except subprocess.TimeoutExpired:
        recv.terminate()
    recv_log.close()

    for name in ("receiver.stdout", "sender.stdout"):
        print(f"--- {name} ---")
        with open(os.path.join(WORK, name)) as f:
            print(f.read())

    if os.path.exists(RECEIVED_FILE):
        with open(RECEIVED_FILE) as f:
            received = f.read()
        print(f"Sent token:     {token}")
        print(f"Received token: {received}")
        if received == token:
            print("RESULT: PASS — LXMF end-to-end encrypted delivery verified over local TCP link")
            return 0
        print("RESULT: FAIL — content mismatch")
        return 1
    print("RESULT: FAIL — no message received")
    return 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "receiver":
        run_receiver(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "sender":
        run_sender(sys.argv[2])
    else:
        sys.exit(orchestrate())
