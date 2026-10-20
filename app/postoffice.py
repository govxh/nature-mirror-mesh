#!/usr/bin/env python3
"""
Nature-Mirror Mesh — Post Office (local LXMF propagation node).

An always-running local node: Reticulum transport + LXMF propagation.
It is the "post office" of the tiny app. When you send a message to
someone who is offline, your app hands the message to the post office;
the post office stores it in its spool and hands it over when the
recipient next logs in and syncs. This is exactly the role a relay /
propagation node plays in the real mesh — here everything runs on one
device over loopback TCP (127.0.0.1). No internet is involved.

The post office has its OWN persistent identity under
app/data/postoffice/ and is never touched by user logins or logouts.

Mechanism (LXMF 1.2.1, verified against the installed library):
  * RNS.Reticulum with enable_transport = True, so the node also
    answers path requests from its announce table. This is how a
    freshly logged-in app learns the public key belonging to an
    offline contact's ID.
  * LXMRouter.enable_propagation() makes this router a propagation
    node. Its propagation destination hash is written to
    data/postoffice/propagation_node.txt; every app backend configures
    it explicitly with LXMRouter.set_outbound_propagation_node(hash)
    and downloads waiting mail with
    LXMRouter.request_messages_from_propagation_node(identity).
  * propagation_cost = 13 (the LXMF minimum) keeps the proof-of-work
    stamp a sender must attach to a stored message small and fast,
    which matters on a phone.

Run directly:   python3 postoffice.py
Normally started by nmm.sh (pidfile: data/postoffice.pid).
"""

import os
import sys
import time
import signal

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
PO_DIR = os.path.join(DATA_DIR, "postoffice")
PN_FILE = os.path.join(PO_DIR, "propagation_node.txt")
PN_PORT = int(os.environ.get("NMM_PN_PORT", "4429"))


def write_config(configdir):
    os.makedirs(configdir, exist_ok=True)
    cfg = f"""[reticulum]
  enable_transport = True
  share_instance = False
  panic_on_interface_error = False

[logging]
  loglevel = 4

[interfaces]
  [[NMM Post Office]]
    type = TCPServerInterface
    enabled = True
    listen_ip = 127.0.0.1
    listen_port = {PN_PORT}
"""
    with open(os.path.join(configdir, "config"), "w") as f:
        f.write(cfg)


def main():
    import RNS
    import LXMF

    os.makedirs(PO_DIR, exist_ok=True)
    configdir = os.path.join(PO_DIR, "config")
    write_config(configdir)

    # Persistent post-office identity (stable propagation node ID).
    identity_file = os.path.join(PO_DIR, "identity")
    if os.path.isfile(identity_file):
        identity = RNS.Identity.from_file(identity_file)
        print(f"[postoffice] loaded identity from {identity_file}", flush=True)
    else:
        identity = RNS.Identity()
        identity.to_file(identity_file)
        print(f"[postoffice] created new identity at {identity_file}", flush=True)

    RNS.Reticulum(configdir=configdir)

    router = LXMF.LXMRouter(
        identity=identity,
        storagepath=os.path.join(PO_DIR, "storage"),
        name="NMM Post Office",
        propagation_cost=13,  # LXMF minimum: fast stamps for senders
    )
    router.enable_propagation()

    pn_hash = RNS.hexrep(router.propagation_destination.hash, delimit=False)
    with open(PN_FILE, "w") as f:
        f.write(pn_hash)
    print(f"[postoffice] propagation node ID: {pn_hash}", flush=True)
    print(f"[postoffice] listening on 127.0.0.1:{PN_PORT} (TCP, loopback only)", flush=True)
    print(f"[postoffice] spool: {router.messagepath}", flush=True)

    stop = {"flag": False}

    def _sigterm(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    last_announce = 0
    last_spool_report = 0
    last_spool_count = -1
    while not stop["flag"]:
        now = time.time()
        if now - last_announce > 15:
            # Announce the propagation destination directly (the router's
            # own announce_propagation_node() has a built-in 20 s delay;
            # direct announces keep freshly started apps fast).
            try:
                router.propagation_destination.announce(
                    app_data=router.get_propagation_node_app_data())
            except Exception as e:
                print(f"[postoffice] announce failed: {e}", flush=True)
            last_announce = now
        if now - last_spool_report > 10:
            count = len(router.propagation_entries)
            if count != last_spool_count:
                print(f"[postoffice] spool holds {count} message(s) "
                      f"for offline recipients", flush=True)
                last_spool_count = count
            last_spool_report = now
        time.sleep(0.5)

    print("[postoffice] shutting down", flush=True)
    try:
        router.exit_handler()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
