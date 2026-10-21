#!/usr/bin/env python3
"""
Nature-Mirror Mesh — tiny app (v1). One file: stdlib web UI + RNS/LXMF.

    python3 nmm_app.py [port]     → the app (default port 8899)
    python3 nmm_app.py backend …  → per-login user backend (internal;
                                    spawned by the web layer, not run
                                    by hand)

How it works
------------
* Your account key is just **2 words** (TESTING ONLY — this is weak on
  purpose for now; it will grow to a 12-word phrase later). The account
  identity is derived deterministically:

      seed     = SHA-512("word1 word2")     (lower-cased, single space)
      identity = RNS.Identity.from_bytes(seed)

  Same 2 words → same identity → same unique ID, on any device.
  Your unique ID is the LXMF delivery destination hash of that identity
  (32 hex characters; the first 16 are shown as the short form).

  New users do not have to invent or type words: the "Create account"
  button (POST /api/autocreate) generates 2 random words from the
  embedded WORDLIST (secrets.choice) and logs in through exactly the
  same derivation path as manual entry, then shows the words and the
  ID so they can be copied and saved.

* Logging in starts a backend process holding that identity. The
  backend connects over loopback TCP to the local Post Office
  (postoffice.py), announces itself, is configured with the post
  office as its LXMF propagation node
  (LXMRouter.set_outbound_propagation_node) and syncs waiting mail
  (LXMRouter.request_messages_from_propagation_node).

* Sending to someone who is offline: the message goes out with
  desired_method = PROPAGATED. The post office stores it in its spool
  ("stored at post office") until the recipient logs in and syncs.

* Logging out kills the backend and deletes the session files — the
  identity is gone from memory. The account's own local data (contacts,
  chat history, LXMF ratchet state) stays under
  app/data/users/<your-id>/, like a phone app keeping its data, and the
  post office spool is never touched by a logout.

* Thread mode (env NMM_THREAD_BACKEND=1 — used inside the Android
  APK, where Chaquopy provides no standalone Python executable to
  spawn): the per-login backend runs on a daemon thread inside the
  web process instead of a subprocess. The file-based IPC
  (cmd.jsonl / ready.json / status.json in the session dir) and the
  session lifecycle are unchanged. Two lifecycle details differ, both
  because the process outlives a login in this mode: all logins share
  the one process-wide Reticulum instance (RNS permits only one per
  process; the client attachment — loopback TCP to the post office,
  same config for every account — is identical for all of them), and
  the backend deregisters its LXMF destinations on shutdown (the
  delivery destination and the router's always-created
  "propagation" destination) so the same account can log in again
  (Transport refuses duplicate registrations). With the env var
  unset, behaviour is exactly the subprocess mode above.
"""

import contextlib
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
PO_DIR = os.path.join(DATA_DIR, "postoffice")
PN_FILE = os.path.join(PO_DIR, "propagation_node.txt")
PO_PIDFILE = os.path.join(DATA_DIR, "postoffice.pid")
PN_PORT = int(os.environ.get("NMM_PN_PORT", "4429"))
CLIENT_RNS_DIR = os.path.join(DATA_DIR, "rns_client")
IDENTITIES_DIR = os.path.join(DATA_DIR, "identities")
USERS_DIR = os.path.join(DATA_DIR, "users")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
DEFAULT_PORT = 8899


def thread_backend_enabled():
    """Thread mode: run the per-login backend on a thread in this
    process instead of spawning a subprocess (Android/Chaquopy has
    no sys.executable to spawn). Selected by env NMM_THREAD_BACKEND=1;
    read at call time so the embedding process can decide at startup.
    """
    return os.environ.get("NMM_THREAD_BACKEND") == "1"


@contextlib.contextmanager
def _tolerate_signal_on_worker_thread():
    """Thread mode only: make signal.signal() tolerant during
    backend startup.

    RNS.Reticulum.__init__ and LXMF.LXMRouter.__init__ both end by
    installing SIGINT/SIGTERM handlers via signal.signal(), which
    raises ValueError when called from a non-main thread — exactly
    where a thread-mode backend runs. Swap in a tolerant wrapper for
    the startup calls: registrations that are legal go through, the
    rest are quietly skipped (signal-based shutdown is not how a
    thread-mode backend is stopped anyway — logout sets its
    stop_flag). This mirrors the Android launcher's process-wide
    shim, scoped to startup. Outside thread mode this is a no-op.
    """
    if not thread_backend_enabled():
        yield
        return
    real_signal = signal.signal

    def _tolerant(signum, handler):
        try:
            return real_signal(signum, handler)
        except (ValueError, OSError):
            return None

    signal.signal = _tolerant
    try:
        yield
    finally:
        signal.signal = real_signal


# ----------------------------------------------------------------------
# Identity derivation (pure — no running Reticulum needed)
# ----------------------------------------------------------------------

def seed_from_words(word1, word2):
    normalised = (word1.strip().lower() + " " + word2.strip().lower())
    return hashlib.sha512(normalised.encode("utf-8")).digest()


def id_from_seed(seed):
    import RNS
    identity = RNS.Identity.from_bytes(seed)
    dest_hash = RNS.Destination.hash(identity, "lxmf", "delivery")
    return RNS.hexrep(dest_hash, delimit=False)


# ----------------------------------------------------------------------
# Wordlist for auto-created accounts
# ----------------------------------------------------------------------
# Simple, concrete, easy-to-spell English words. Homophones and
# easily confused spellings (sun/son, sea/see, rain/reign, pear/pair…)
# are deliberately excluded: a word the user copies down must be the
# word they type back. 2 words from this list is a TESTING-grade key
# (see the module docstring) — the list exists so a new user can get
# an account with zero typing, not to make the key strong.
WORDLIST = (
    "apple", "river", "tiger", "moon", "forest", "ocean", "lake",
    "valley", "desert", "island", "cloud", "storm", "wind", "snow",
    "leaf", "tree", "rock", "stone", "sand", "wave", "star", "sky",
    "field", "meadow", "garden", "flower", "rose", "tulip", "daisy",
    "lily", "grass", "fern", "moss", "pine", "oak", "elm", "bamboo",
    "cactus", "coral", "pearl", "amber", "ruby", "opal", "jade",
    "ivory", "maple", "cedar", "willow", "birch", "violet", "lilac",
    "orchard", "harbor", "lagoon", "canyon", "cliff", "cave", "hill",
    "pond", "stream", "brook", "path", "trail", "camp", "farm",
    "barn", "gate", "wall", "roof", "beach", "coast", "lion",
    "zebra", "panda", "koala", "camel", "donkey", "monkey", "rabbit",
    "turtle", "eagle", "owl", "falcon", "sparrow", "robin", "duck",
    "goose", "swan", "frog", "bear", "wolf", "fox", "deer", "goat",
    "sheep", "horse", "mouse", "fish", "shark", "whale", "crab",
    "snail", "bee", "ant", "moth", "beetle", "cat", "dog", "cow",
    "pig", "table", "chair", "door", "window", "key", "lock",
    "bell", "book", "paper", "card", "coin", "ring", "cup", "mug",
    "plate", "bowl", "spoon", "bottle", "basket", "box", "bag",
    "hat", "cap", "shoe", "sock", "shirt", "coat", "glove",
    "scarf", "clock", "lamp", "candle", "mirror", "brush", "comb",
    "soap", "towel", "pillow", "blanket", "desk", "shelf", "ladder",
    "rope", "chain", "wheel", "boat", "train", "kite", "ball",
    "drum", "jet", "bus", "car", "bike", "bread", "rice", "milk",
    "cheese", "egg", "honey", "sugar", "salt", "lemon", "mango",
    "banana", "grape", "peach", "melon", "cake", "tea", "coffee",
    "home", "city", "town", "village", "road", "bridge", "tower",
    "castle", "house", "room", "hall", "shop", "market", "school",
    "park", "compass", "anchor", "lantern", "hammer", "bucket",
    "shovel", "wagon", "saddle", "feather", "button", "pocket",
    "ribbon", "marble", "pebble", "shell", "happy", "sunny",
    "quiet", "gentle", "brave", "clever", "kind", "warm", "cool",
    "bright", "swift", "calm", "proud", "merry", "sing", "dance",
    "jump", "swim", "climb", "read", "play", "smile", "dream",
    "wish", "hope", "laugh", "sleep", "wake", "grow", "shine",
    "rain", "dawn", "dusk", "frost", "flame", "spark", "grove",
    "reef", "dune", "mesa", "bay", "cape", "inlet", "marsh",
    "heath",
)


def generate_words():
    """Two random words for a brand-new account (auto-create)."""
    return secrets.choice(WORDLIST), secrets.choice(WORDLIST)


def publish_identity(identity, user_id):
    """Write this account's PUBLIC key into the on-device identity
    directory (see recall_identity for why). Public keys are public
    by design in Reticulum — announces broadcast them to everyone;
    this directory is just the app remembering, on this device,
    what it is allowed to know."""
    try:
        os.makedirs(IDENTITIES_DIR, exist_ok=True)
        final = os.path.join(IDENTITIES_DIR, user_id + ".pub")
        tmp = final + ".tmp"
        with open(tmp, "wb") as f:
            f.write(identity.get_public_key())
        os.replace(tmp, final)
    except Exception as e:
        print(f"[backend] identity publish failed: {e}", flush=True)


def recall_identity(to_hash):
    """Best-effort RNS Identity for a destination hash WITHOUT
    needing a live path to it: (a) RNS's own recall (announces this
    process has heard / known destinations it loaded), then (b) the
    on-device identity directory — every account that has ever
    logged in on this device published its public key there.

    Why (b) exists: a PROPAGATED message needs the recipient's
    identity (to encrypt to) and a path to the PROPAGATION NODE —
    never a live path to the recipient. But the post office cannot
    reliably answer path requests for an offline contact: RNS culls
    a path-table entry as soon as the interface it was learned on
    disappears (“Path … was removed since the attached interface no
    longer exists”), and an offline contact's only interface was its
    own now-closed connection. Waiting for that path is therefore a
    race — observed intermittently failing acceptance flows with
    “failed: ID not found (no path)” after the full 240 s wait,
    while the post office logged “Ignoring path request …, no path
    known” for a destination that had announced to it directly
    (instrumented repro, 2026-10-21). The identity directory removes
    the race for every account that has ever logged in on this
    device; the path-request loop in do_send remains as fallback
    for IDs never seen on this device."""
    import RNS
    ident = RNS.Identity.recall(to_hash)
    if ident is not None:
        return ident
    try:
        path = os.path.join(
            IDENTITIES_DIR,
            RNS.hexrep(to_hash, delimit=False) + ".pub")
        with open(path, "rb") as f:
            pub = f.read()
        ident = RNS.Identity(create_keys=False)
        ident.load_public_key(pub)
        if RNS.Destination.hash(ident, "lxmf", "delivery") != to_hash:
            return None
        return ident
    except Exception:
        return None


def atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


# ======================================================================
# BACKEND MODE — one process per login, holds the user's identity
# ======================================================================

def write_client_config(configdir):
    os.makedirs(configdir, exist_ok=True)
    cfg = f"""[reticulum]
  enable_transport = False
  share_instance = False
  panic_on_interface_error = False

[logging]
  loglevel = 4

[interfaces]
  [[NMM Post Office]]
    type = TCPClientInterface
    enabled = True
    target_host = 127.0.0.1
    target_port = {PN_PORT}
"""
    with open(os.path.join(configdir, "config"), "w") as f:
        f.write(cfg)


class Backend:
    SYNC_IDLE_STATES = None  # filled in run() once LXMF is imported

    def __init__(self, seed, session_dir):
        self.seed = seed
        self.session_dir = session_dir
        self.cmd_file = os.path.join(session_dir, "cmd.jsonl")
        self.ready_file = os.path.join(session_dir, "ready.json")
        self.status_file = os.path.join(session_dir, "status.json")
        self.user_id = id_from_seed(seed)
        self.user_dir = os.path.join(USERS_DIR, self.user_id)
        os.makedirs(self.user_dir, exist_ok=True)
        self.inbox_file = os.path.join(self.user_dir, "inbox.json")
        self.sent_file = os.path.join(self.user_dir, "sent.json")
        self.stop_flag = False
        self.router = None
        self.identity = None
        self.delivery = None
        self.pn_hash = None
        self.inbox = read_json(self.inbox_file, [])
        self.inbox_hashes = {m.get("hash") for m in self.inbox}
        self.sent_entries = {e["local_id"]: e
                             for e in read_json(self.sent_file, [])}
        self.tracked = {}          # local_id -> LXMessage
        self.lock = threading.Lock()
        self.last_sync_request = 0

    # ---- LXMF delivery callback -------------------------------------
    def on_message(self, message):
        import RNS
        try:
            content = message.content_as_string()
        except Exception:
            content = message.content.decode("utf-8", "replace")
        entry = {
            "hash": RNS.hexrep(message.hash, delimit=False),
            "from": RNS.hexrep(message.source_hash, delimit=False),
            "content": content,
            "time": time.time(),
        }
        with self.lock:
            if entry["hash"] in self.inbox_hashes:
                return
            self.inbox_hashes.add(entry["hash"])
            self.inbox.append(entry)
            atomic_write_json(self.inbox_file, self.inbox)
        print(f"[backend] message received from {entry['from'][:16]}…: "
              f"{content!r}", flush=True)

    # ---- sending ------------------------------------------------------
    def status_text(self, msg):
        import LXMF
        st = msg.state
        if st == LXMF.LXMessage.FAILED:
            return "failed"
        if st == LXMF.LXMessage.REJECTED:
            return "rejected"
        if st == LXMF.LXMessage.DELIVERED:
            return "delivered"
        if st == LXMF.LXMessage.SENT:
            if msg.desired_method == LXMF.LXMessage.PROPAGATED:
                return "stored at post office"
            return "sent"
        if st == LXMF.LXMessage.SENDING:
            return "sending"
        return "queued"

    def refresh_sent_file(self):
        import RNS
        changed = False
        with self.lock:
            items = list(self.tracked.items())
        for local_id, msg in items:
            entry = self.sent_entries.get(local_id)
            if entry is None:
                continue
            new_status = self.status_text(msg)
            new_hash = (RNS.hexrep(msg.hash, delimit=False)
                        if msg.hash else entry.get("lxmf_hash"))
            if entry.get("status") != new_status or \
               entry.get("lxmf_hash") != new_hash:
                entry["status"] = new_status
                entry["lxmf_hash"] = new_hash
                changed = True
        if changed:
            with self.lock:
                atomic_write_json(
                    self.sent_file,
                    sorted(self.sent_entries.values(),
                           key=lambda e: e["time"]))

    def do_send(self, local_id, to_hex, content):
        import RNS
        import LXMF
        entry = self.sent_entries[local_id]
        try:
            to_hash = bytes.fromhex(to_hex)
        except Exception:
            entry["status"] = "failed: bad ID"
            self.refresh_sent_file()
            return
        # Learn the recipient's public key (needed to encrypt the
        # propagated message). First try WITHOUT any path at all —
        # RNS recall / the on-device identity directory (see
        # recall_identity: a live path to an offline contact is
        # culled by RNS when the contact disconnects, so requiring
        # one is a race). Only if the identity is genuinely unknown
        # on this device, ask the network: the post office answers
        # path requests from its announce table while that table
        # still holds the contact, and each answer also teaches us
        # the identity for next time. That wait is deliberately
        # patient (240 s): path answers ride the announce retransmit
        # cadence and can take a minute or more — this system is
        # delay-tolerant by design, so the send waits.
        dest_identity = recall_identity(to_hash)
        deadline = time.time() + 240
        while dest_identity is None and time.time() < deadline and \
                not self.stop_flag:
            RNS.Transport.request_path(to_hash)
            time.sleep(1)
            dest_identity = recall_identity(to_hash)
        if dest_identity is None:
            entry["status"] = "failed: ID not found (no path)"
            with self.lock:
                atomic_write_json(
                    self.sent_file,
                    sorted(self.sent_entries.values(),
                           key=lambda e: e["time"]))
            print(f"[backend] send {local_id}: no path to {to_hex}",
                  flush=True)
            return
        dest = RNS.Destination(dest_identity, RNS.Destination.OUT,
                               RNS.Destination.SINGLE, "lxmf", "delivery")
        msg = LXMF.LXMessage(dest, self.delivery, content=content,
                             title="nmm",
                             desired_method=LXMF.LXMessage.PROPAGATED)
        with self.lock:
            self.tracked[local_id] = msg
        self.router.handle_outbound(msg)
        print(f"[backend] send {local_id}: handed to router "
              f"(propagated via post office)", flush=True)

    def handle_cmd(self, cmd):
        ctype = cmd.get("type")
        if ctype == "send":
            local_id = cmd["local_id"]
            with self.lock:
                self.sent_entries[local_id] = {
                    "local_id": local_id,
                    "lxmf_hash": None,
                    "to": cmd["to"],
                    "content": cmd["content"],
                    "status": "queued",
                    "time": time.time(),
                }
                atomic_write_json(
                    self.sent_file,
                    sorted(self.sent_entries.values(),
                           key=lambda e: e["time"]))
            threading.Thread(target=self.do_send,
                             args=(local_id, cmd["to"], cmd["content"]),
                             daemon=True).start()
        elif ctype == "sync":
            self.request_sync(force=True)

    def request_sync(self, force=False):
        import LXMF
        if self.pn_hash is None:
            return
        idle = (LXMF.LXMRouter.PR_IDLE, LXMF.LXMRouter.PR_COMPLETE,
                LXMF.LXMRouter.PR_NO_PATH, LXMF.LXMRouter.PR_LINK_FAILED,
                LXMF.LXMRouter.PR_TRANSFER_FAILED)
        state = self.router.propagation_transfer_state
        if state in idle and (force or
                              time.time() - self.last_sync_request > 15):
            self.last_sync_request = time.time()
            print(f"[backend] requesting waiting messages from post "
                  f"office (state was {state})", flush=True)
            self.router.request_messages_from_propagation_node(
                self.identity)

    # ---- main ---------------------------------------------------------
    def run(self):
        import RNS
        import LXMF

        os.makedirs(CLIENT_RNS_DIR, exist_ok=True)
        write_client_config(CLIENT_RNS_DIR)
        # The tolerant-signal wrapper covers the RNS/LXMF constructor
        # calls below in thread mode (see its docstring); in
        # subprocess mode it is a no-op and everything runs as before.
        with _tolerate_signal_on_worker_thread():
            if RNS.Reticulum.get_instance() is None:
                RNS.Reticulum(configdir=CLIENT_RNS_DIR)
            # Thread mode only: a previous login in this same process
            # already started Reticulum (RNS raises on a second
            # instance). The client attachment is shared — same
            # config, same loopback TCP interface to the post office,
            # for every account. In subprocess mode the backend
            # process is always fresh, so the instance is always
            # created here, exactly as before.

            self.identity = RNS.Identity.from_bytes(self.seed)
            # Router storage is per-account and persistent (like an
            # app keeping its data): LXMF ratchet state lives there
            # and must survive logouts, or old announces could not
            # be decrypted.
            self.router = LXMF.LXMRouter(
                identity=self.identity,
                storagepath=self.user_dir)
            self.delivery = self.router.register_delivery_identity(
                self.identity, display_name="NMM user", stamp_cost=None)
            self.router.register_delivery_callback(self.on_message)

        real_id = RNS.hexrep(self.delivery.hash, delimit=False)
        assert real_id == self.user_id, (real_id, self.user_id)
        print(f"[backend] logged in, ID = {real_id}", flush=True)
        # Publish our public key to the on-device identity directory
        # so future senders on this device can encrypt a propagated
        # message to us even while we are offline (see
        # recall_identity).
        publish_identity(self.identity, real_id)

        # Configure the post office as our propagation node (explicit
        # configuration mechanism of LXMF 1.2.1).
        if os.path.isfile(PN_FILE):
            with open(PN_FILE) as f:
                self.pn_hash = bytes.fromhex(f.read().strip())
            self.router.set_outbound_propagation_node(self.pn_hash)
            print(f"[backend] outbound propagation node set to "
                  f"{RNS.hexrep(self.pn_hash, delimit=False)}",
                  flush=True)
            deadline = time.time() + 40
            while not RNS.Transport.has_path(self.pn_hash) and \
                    time.time() < deadline:
                RNS.Transport.request_path(self.pn_hash)
                time.sleep(0.5)
            print(f"[backend] path to post office: "
                  f"{RNS.Transport.has_path(self.pn_hash)}", flush=True)
        else:
            print("[backend] WARNING: post office file not found — "
                  "is postoffice.py running?", flush=True)

        self.router.announce(self.delivery.hash)
        self.request_sync(force=True)
        atomic_write_json(self.ready_file,
                          {"id": real_id, "time": time.time()})

        def _sigterm(signum, frame):
            self.stop_flag = True

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, _sigterm)
            signal.signal(signal.SIGINT, _sigterm)
        # Thread mode: signal.signal() is main-thread-only and would
        # raise here. Logout instead stops this backend by setting
        # stop_flag directly (see ThreadBackendHandle.terminate) —
        # the same flag the signal handler above sets, honoured by
        # the same loop below.

        cmd_offset = 0
        last_announce = time.time()
        last_status = 0
        while not self.stop_flag:
            # commands from the web layer
            try:
                if os.path.isfile(self.cmd_file):
                    with open(self.cmd_file) as f:
                        f.seek(cmd_offset)
                        lines = f.readlines()
                        cmd_offset = f.tell()
                    for line in lines:
                        line = line.strip()
                        if line:
                            try:
                                self.handle_cmd(json.loads(line))
                            except Exception as e:
                                print(f"[backend] cmd error: {e}",
                                      flush=True)
            except Exception as e:
                print(f"[backend] cmd poll error: {e}", flush=True)

            if time.time() - last_announce > 20:
                try:
                    self.router.announce(self.delivery.hash)
                except Exception:
                    pass
                last_announce = time.time()

            self.request_sync()
            self.refresh_sent_file()

            if time.time() - last_status > 2:
                atomic_write_json(self.status_file, {
                    "id": real_id,
                    "pn_path": bool(self.pn_hash is not None and
                                    RNS.Transport.has_path(self.pn_hash)),
                    "transfer_state":
                        self.router.propagation_transfer_state,
                    "time": time.time(),
                })
                last_status = time.time()
            time.sleep(0.4)

        print("[backend] shutting down", flush=True)
        try:
            self.router.exit_handler()
        except Exception:
            pass
        if thread_backend_enabled():
            # The process outlives this backend in thread mode. LXMF's
            # exit_handler() leaves this router's IN destinations
            # registered with Transport — BOTH the delivery destination
            # and the "propagation" destination LXMRouter.__init__
            # always creates for its identity — and Transport raises
            # KeyError on a second registration of the same hash, so
            # re-login of this account in this process would fail in
            # the next router's constructor. Free both registrations.
            # (Subprocess mode: the process exits now, so this is
            # skipped and behaviour is unchanged.)
            for dest in (self.delivery,
                         getattr(self.router, "propagation_destination",
                                 None)):
                if dest is not None:
                    try:
                        RNS.Transport.deregister_destination(dest)
                    except Exception:
                        pass
        return 0


def run_backend(argv):
    # argv: backend --session <dir>   (seed arrives via env NMM_SEED_HEX)
    session_dir = argv[argv.index("--session") + 1]
    seed = bytes.fromhex(os.environ["NMM_SEED_HEX"])
    return Backend(seed, session_dir).run()


# ======================================================================
# WEB MODE
# ======================================================================

SESSION = {"proc": None, "session_dir": None, "user_id": None,
           "seed": None, "words": None}
SESSION_LOCK = threading.Lock()


class ThreadBackendHandle:
    """Popen-shaped handle for a Backend running on a daemon thread.

    Used in thread mode (NMM_THREAD_BACKEND=1) — inside the Android
    APK there is no standalone Python executable, so the per-login
    backend cannot be spawned with subprocess.Popen. This exposes the
    subset of the Popen interface the web layer uses — poll(),
    terminate(), wait(), kill() — so the login/logout/session code is
    identical in both modes. Stopping is cooperative: terminate()
    sets the backend's stop_flag, the very flag the SIGTERM handler
    sets in subprocess mode, and the backend's main loop honours it;
    wait() joins the thread. A thread cannot be force-killed, so
    kill() is the same cooperative stop (logout proceeds after its
    wait timeout either way, exactly as with a killed subprocess).
    """

    def __init__(self, backend):
        self._backend = backend
        self.error = None
        self._thread = threading.Thread(target=self._run,
                                        name="nmm-backend",
                                        daemon=True)

    def _run(self):
        try:
            self._backend.run()
        except Exception as e:
            self.error = e
            print(f"[app] backend thread error: {e!r}", flush=True)

    def start(self):
        self._thread.start()
        return self

    def poll(self):
        return None if self._thread.is_alive() else 0

    def terminate(self):
        self._backend.stop_flag = True

    def kill(self):
        self._backend.stop_flag = True

    def wait(self, timeout=None):
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise subprocess.TimeoutExpired("nmm-backend-thread",
                                            timeout)
        return 0


def ensure_postoffice():
    """Start the post office if it is not already running (pidfile)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.isfile(PO_PIDFILE):
        try:
            with open(PO_PIDFILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return pid
        except Exception:
            pass
    log = open(os.path.join(DATA_DIR, "postoffice.log"), "ab")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(APP_DIR, "postoffice.py")],
        stdout=log, stderr=subprocess.STDOUT)
    with open(PO_PIDFILE, "w") as f:
        f.write(str(proc.pid))
    print(f"[app] started post office (pid {proc.pid})")
    return proc.pid


def user_file(user_id, name, default):
    return read_json(os.path.join(USERS_DIR, user_id, name), default)


class Handler:
    pass


def make_handler():
    from http.server import BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode())

        def do_GET(self):
            if self.path == "/":
                body = INDEX_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type",
                                 "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state":
                self._json(200, api_state())
            elif self.path == "/api/health":
                self._json(200, api_health())
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            try:
                data = self._body()
                if self.path == "/api/login":
                    self._json(*api_login(data))
                elif self.path == "/api/autocreate":
                    self._json(*api_autocreate())
                elif self.path == "/api/logout":
                    self._json(*api_logout())
                elif self.path == "/api/contacts":
                    self._json(*api_add_contact(data))
                elif self.path == "/api/send":
                    self._json(*api_send(data))
                elif self.path == "/api/sync":
                    self._json(*api_sync())
                else:
                    self._json(404, {"error": "not found"})
            except Exception as e:
                self._json(500, {"error": str(e)})

    return H


def api_state():
    with SESSION_LOCK:
        active = SESSION["proc"] is not None and \
            SESSION["proc"].poll() is None
        user_id = SESSION["user_id"] if active else None
        session_dir = SESSION["session_dir"]
        words = SESSION["words"] if active else None
    state = {
        "logged_in": bool(active),
        "postoffice_file": os.path.isfile(PN_FILE),
    }
    if active and user_id:
        state["id"] = user_id
        state["short_id"] = user_id[:16]
        if words:
            # The current session's 2 words, so the UI's "Your
            # account" panel (words + ID, with Copy buttons) survives
            # its periodic re-renders. This is the local UI on the
            # user's own device — the same trust boundary as the
            # backend process itself.
            state["words"] = list(words)
        state["contacts"] = user_file(user_id, "contacts.json", [])
        state["inbox"] = user_file(user_id, "inbox.json", [])
        state["sent"] = user_file(user_id, "sent.json", [])
        if session_dir:
            state["backend"] = read_json(
                os.path.join(session_dir, "status.json"), {})
    return state


def api_health():
    """Lightweight status for the UI's status line: is the post
    office actually reachable on its loopback port, and (when logged
    in) what stage is the session backend at. Reuses the existing
    IPC files (ready.json / status.json) — no parallel system."""
    try:
        s = socket.create_connection(("127.0.0.1", PN_PORT), 0.35)
        s.close()
        po_up = True
    except Exception:
        po_up = False
    with SESSION_LOCK:
        active = SESSION["proc"] is not None and \
            SESSION["proc"].poll() is None
        session_dir = SESSION["session_dir"]
        user_id = SESSION["user_id"] if active else None
    health = {
        "app": "up",
        "postoffice": "connected" if po_up else "not found",
        "postoffice_file": os.path.isfile(PN_FILE),
        "logged_in": bool(active),
    }
    if active and session_dir:
        health["id"] = user_id
        health["backend_ready"] = os.path.isfile(
            os.path.join(session_dir, "ready.json"))
        health["backend"] = read_json(
            os.path.join(session_dir, "status.json"), {})
    return health


def api_login(data):
    word1 = (data.get("word1") or "").strip()
    word2 = (data.get("word2") or "").strip()
    if not word1 or not word2:
        return 400, {"error": "two words are required"}
    return _start_session(word1, word2)


def api_autocreate():
    """Create a brand-new account with ZERO typing: generate 2
    random words and log in through exactly the same derivation and
    session path as manual entry (api_login → _start_session →
    seed_from_words). Returns the words so the UI can show them for
    saving/copying."""
    word1, word2 = generate_words()
    code, obj = _start_session(word1, word2)
    if code == 200:
        obj = dict(obj)
        obj["word1"] = word1
        obj["word2"] = word2
        obj["autocreated"] = True
    return code, obj


def _start_session(word1, word2):
    with SESSION_LOCK:
        if SESSION["proc"] is not None and \
                SESSION["proc"].poll() is None:
            return 409, {"error": "already logged in — log out first"}
        seed = seed_from_words(word1, word2)
        user_id = id_from_seed(seed)
        session_dir = os.path.join(
            SESSIONS_DIR, f"{user_id[:12]}-{int(time.time())}")
        os.makedirs(session_dir, exist_ok=True)
        if thread_backend_enabled():
            # No subprocess to spawn (Android/Chaquopy): run the same
            # Backend on a daemon thread in this process. Same session
            # dir, same seed, same file IPC — only the carrier differs.
            backend = Backend(seed, session_dir)
            handle = ThreadBackendHandle(backend).start()
            SESSION.update(proc=handle, session_dir=session_dir,
                           user_id=user_id, seed=seed,
                           words=(word1.strip().lower(),
                                  word2.strip().lower()))
        else:
            env = dict(os.environ)
            env["NMM_SEED_HEX"] = seed.hex()
            log = open(os.path.join(session_dir, "backend.log"), "wb")
            proc = subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "backend",
                 "--session", session_dir],
                env=env, stdout=log, stderr=subprocess.STDOUT)
            SESSION.update(proc=proc, session_dir=session_dir,
                           user_id=user_id, seed=seed,
                           words=(word1.strip().lower(),
                                  word2.strip().lower()))
    # Wait for the backend to be ready (identity live, post office set).
    ready_file = os.path.join(session_dir, "ready.json")
    deadline = time.time() + 90
    while time.time() < deadline:
        if os.path.isfile(ready_file):
            ready = read_json(ready_file, {})
            return 200, {"id": ready.get("id", user_id),
                         "short_id": ready.get("id", user_id)[:16]}
        if SESSION["proc"].poll() is not None:
            return 500, {"error": "backend exited during login; see "
                                  "session backend.log"}
        time.sleep(0.25)
    return 504, {"error": "backend did not become ready in 90 s"}


def api_logout():
    with SESSION_LOCK:
        proc = SESSION["proc"]
        session_dir = SESSION["session_dir"]
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        # "Clear data": identity + session files are dropped. The
        # account's own local data under data/users/<id>/ stays (like a
        # phone app keeping its data); the post office is untouched.
        if session_dir and os.path.isdir(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
        SESSION.update(proc=None, session_dir=None, user_id=None,
                       seed=None, words=None)
    return 200, {"ok": True}


def api_add_contact(data):
    with SESSION_LOCK:
        user_id = SESSION["user_id"]
    if not user_id:
        return 401, {"error": "not logged in"}
    cid = (data.get("id") or "").strip().lower()
    name = (data.get("name") or "").strip() or cid[:16]
    try:
        bytes.fromhex(cid)
        assert len(cid) == 32
    except Exception:
        return 400, {"error": "ID must be 32 hex characters"}
    path = os.path.join(USERS_DIR, user_id, "contacts.json")
    contacts = read_json(path, [])
    contacts = [c for c in contacts if c["id"] != cid]
    contacts.append({"id": cid, "name": name})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, contacts)
    return 200, {"ok": True, "contacts": contacts}


def _append_cmd(cmd):
    with SESSION_LOCK:
        session_dir = SESSION["session_dir"]
        proc = SESSION["proc"]
    if not session_dir or proc is None or proc.poll() is not None:
        return False
    with open(os.path.join(session_dir, "cmd.jsonl"), "a") as f:
        f.write(json.dumps(cmd) + "\n")
    return True


def api_send(data):
    with SESSION_LOCK:
        user_id = SESSION["user_id"]
    if not user_id:
        return 401, {"error": "not logged in"}
    to = (data.get("to") or "").strip().lower()
    content = data.get("content") or ""
    try:
        bytes.fromhex(to)
        assert len(to) == 32
    except Exception:
        return 400, {"error": "recipient ID must be 32 hex characters"}
    if not content.strip():
        return 400, {"error": "message is empty"}
    local_id = uuid.uuid4().hex[:12]
    if not _append_cmd({"type": "send", "local_id": local_id,
                        "to": to, "content": content}):
        return 500, {"error": "backend not running"}
    return 200, {"ok": True, "local_id": local_id}


def api_sync():
    if not _append_cmd({"type": "sync"}):
        return 500, {"error": "backend not running"}
    return 200, {"ok": True}


INDEX_HTML = """<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nature-Mirror Mesh</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#0e1512;color:#e8f0ea}
 .wrap{max-width:640px;margin:0 auto;padding:16px}
 h1{font-size:20px} .card{background:#16211b;border:1px solid #24402f;border-radius:12px;padding:14px;margin:12px 0}
 input,button,textarea{font-size:16px;padding:9px;border-radius:8px;border:1px solid #33513d;background:#0e1512;color:#e8f0ea;-webkit-user-select:text;user-select:text}
 button{background:#1e4630;cursor:pointer} button:hover{background:#27603f}
 button:disabled{opacity:.45;cursor:wait}
 .big{font-size:18px;padding:14px;width:100%;background:#27603f}
 .mono{font-family:monospace;word-break:break-all}
 input[readonly]{background:#101a13}
 .small{font-size:13px;color:#9db8a6}
 .warn{color:#ffd27d;font-size:14px}
 .msg{margin:6px 0;padding:8px 10px;border-radius:10px;max-width:85%}
 .mine{background:#1e4630;margin-left:auto} .theirs{background:#1a2630;margin-right:auto}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center} .row>*{flex:1}
 .row .copybtn{flex:0 0 auto}
 .contact{padding:8px;border:1px solid #33513d;border-radius:8px;margin:4px 0;cursor:pointer;background:none;width:100%;text-align:left;color:#e8f0ea}
 .contact.sel{background:#1e4630}
 #err{display:none;background:#4a1d1d;border:1px solid #8a3b3b;color:#ffb4b4;border-radius:10px;padding:10px 12px;margin:12px 0;font-size:14px}
 #busy{color:#ffd27d;min-height:18px}
</style>
<div class="wrap">
 <h1>🌿 Nature-Mirror Mesh <span class="small">app v0.1.2</span></h1>
 <div id="status" class="card small">⏳ Starting…</div>
 <div id="err"></div>
 <div id="busy" class="small"></div>
 <div id="app"><div class="card">⏳ Starting…</div></div>
 <p class="small">Offline-first chat. Messages for offline friends wait
 at your local Post Office until they log in. An account key is just
 2 words — <b>for testing only</b>, never use it for anything valuable.</p>
</div>
<script>
let state=null, selected=null, lastSig=null, lastLoggedIn=null;

async function api(path, data){
  let r;
  try{
    r = await fetch(path, data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});
  }catch(e){
    return {error:'could not reach the app server ('+e.message+') — is the app still starting?'};
  }
  try{ return await r.json(); }
  catch(e){ return {error:'server answered HTTP '+r.status+' with an unreadable reply'}; }
}
function esc(s){return (s||'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function showErr(msg){ const e=document.getElementById('err'); e.textContent='⚠ '+msg; e.style.display='block'; }
function clearErr(){ const e=document.getElementById('err'); e.textContent=''; e.style.display='none'; }
function setBusy(on, msg){
  document.querySelectorAll('button').forEach(b=>b.disabled=on);
  document.getElementById('busy').textContent = on ? ('⏳ '+(msg||'Working…')) : '';
}

/* ------------------------------------------------------------------
   Re-render safety — the v0.1.1 device bug (confirmed root cause):
   the old page rebuilt #app's innerHTML every 2.5 s unconditionally,
   erasing whatever the user was typing into the word fields. Now:
   (1) a rebuild happens ONLY when the rendered state actually
       changed (signature compare);
   (2) a rebuild NEVER happens while the user is typing in a text
       field, unless the login state itself flipped (then it must);
   (3) when a rebuild does happen, every input's value, the focused
       element and its selection are captured first and restored
       after — typing survives rendering, always.
------------------------------------------------------------------ */
function stateSig(st){
  const b = st.backend||{};
  return JSON.stringify({l:st.logged_in, id:st.id||null, w:st.words||null,
    pf:st.postoffice_file, pn:!!b.pn_path, ts:b.transfer_state,
    c:st.contacts||[], i:st.inbox||[], s:st.sent||[], sel:selected});
}
function captureInputs(){
  const cap={values:{}, focusId:null, selStart:null, selEnd:null};
  document.querySelectorAll('#app input, #app textarea').forEach(el=>{
    if(el.id) cap.values[el.id]=el.value;
  });
  const ae=document.activeElement;
  if(ae && ae.id && document.getElementById('app').contains(ae)){
    cap.focusId=ae.id;
    try{ cap.selStart=ae.selectionStart; cap.selEnd=ae.selectionEnd; }catch(e){}
  }
  return cap;
}
function restoreInputs(cap){
  Object.keys(cap.values).forEach(id=>{
    const el=document.getElementById(id);
    if(el && el.value!==cap.values[id]) el.value=cap.values[id];
  });
  if(cap.focusId){
    const el=document.getElementById(cap.focusId);
    if(el){ el.focus();
      if(cap.selStart!==null && el.setSelectionRange){
        try{ el.setSelectionRange(cap.selStart, cap.selEnd); }catch(e){}
      }
    }
  }
}
function userIsTyping(){
  const ae=document.activeElement;
  return !!(ae && (ae.tagName==='INPUT'||ae.tagName==='TEXTAREA')
            && document.getElementById('app').contains(ae));
}

async function refresh(){
  const r = await api('/api/state');
  if(r && !r.error){ state=r; render(); }
  else{
    showErr('Status check failed: '+((r&&r.error)||'unknown error'));
    if(!state){ state={logged_in:false}; render(); }
  }
}
async function pollHealth(){
  const el=document.getElementById('status');
  let h;
  try{ const r=await fetch('/api/health'); h=await r.json(); }
  catch(e){ el.textContent='⏳ Starting… (waiting for the app server)'; return; }
  let t = (h.postoffice==='connected')
    ? 'Post office: connected ✓'
    : 'Post office: not found — it starts by itself, give it a moment';
  if(h.logged_in){
    t += ' · Logged in';
    if(h.backend && h.backend.pn_path) t += ' · Post office link: live ✓';
    else if(h.backend_ready===false) t += ' · Backend: starting…';
    else t += ' · Post office link: connecting…';
  } else {
    t += ' · Not logged in';
  }
  el.textContent=t;
}

function render(force){
  if(!state) return;
  const sig = stateSig(state);
  const loginChanged = (lastLoggedIn !== state.logged_in);
  if(!force){
    if(sig===lastSig && !loginChanged) return;      // nothing changed: no rebuild
    if(userIsTyping() && !loginChanged) return;     // never rebuild under the user's fingers
  }
  const cap = captureInputs();
  lastSig = sig; lastLoggedIn = state.logged_in;
  const el = document.getElementById('app');
  if(!state.logged_in){
    el.innerHTML = `<div class="card"><h3>New here?</h3>
      <p><button class="big" onclick="autoCreate()">✨ Create account</button></p>
      <p class="small">No typing needed — the app invents your 2 secret
      words for you and shows them so you can save them.</p></div>
     <div class="card"><h3>Returning? Log in with your 2 words</h3>
      <div class="row"><input id="w1" placeholder="word one" type="text" inputmode="text" autocomplete="off" autocapitalize="none" spellcheck="false">
      <input id="w2" placeholder="word two" type="text" inputmode="text" autocomplete="off" autocapitalize="none" spellcheck="false"></div>
      <p><button onclick="login()">Create / Log in</button></p>
      <p class="small">Same 2 words always bring back the same account
      and the same unique ID.</p></div>`;
    restoreInputs(cap);
    return;
  }
  const contacts = state.contacts||[];
  if(selected && !contacts.find(c=>c.id===selected)) selected=null;
  let conv = [];
  (state.inbox||[]).filter(m=>m.from===selected).forEach(m=>conv.push({mine:false,text:m.content,time:m.time,st:''}));
  (state.sent||[]).filter(m=>m.to===selected).forEach(m=>conv.push({mine:true,text:m.content,time:m.time,st:m.status}));
  conv.sort((a,b)=>a.time-b.time);
  const w = state.words;
  const accountPanel = w ? `
   <div class="card"><h3>🔑 Your account — save this!</h3>
    <div class="small">Your 2 secret words</div>
    <div class="row"><input id="aw1" class="mono" readonly value="${esc(w[0])}" onclick="this.select()">
    <button class="copybtn" onclick="copyEl('aw1',this)">Copy</button></div>
    <div class="row"><input id="aw2" class="mono" readonly value="${esc(w[1])}" onclick="this.select()">
    <button class="copybtn" onclick="copyEl('aw2',this)">Copy</button></div>
    <div class="small">Your unique ID</div>
    <div class="row"><input id="aid" class="mono" readonly value="${state.id}" onclick="this.select()">
    <button class="copybtn" onclick="copyEl('aid',this)">Copy</button></div>
    <p class="warn">Save these 2 words — they are your only key.
    Anyone with them has your account.</p>
    <div class="small">short: ${state.short_id}… · post office:
    ${state.backend && state.backend.pn_path ? 'connected ✓' : 'connecting…'}</div>
    <p class="row"><button onclick="syncNow()">Sync now</button>
    <button onclick="logout()">Log out / clear data</button></p></div>` : `
   <div class="card"><div class="small">Your unique ID</div>
    <div class="mono">${state.id}</div>
    <div class="small">short: ${state.short_id}… · post office:
    ${state.backend && state.backend.pn_path ? 'connected ✓' : 'connecting…'}</div>
    <p class="row"><button onclick="syncNow()">Sync now</button>
    <button onclick="logout()">Log out / clear data</button></p></div>`;
  el.innerHTML = accountPanel + `
   <div class="card"><h3>Contacts</h3>
    ${contacts.map(c=>`<button class="contact ${c.id===selected?'sel':''}" onclick="sel('${c.id}')">${esc(c.name)} <span class="mono small">${c.id.slice(0,16)}…</span></button>`).join('') || '<p class="small">No contacts yet.</p>'}
    <div class="row"><input id="cid" placeholder="contact ID (32 hex)" type="text" inputmode="text" autocomplete="off" autocapitalize="none" spellcheck="false">
    <input id="cname" placeholder="name" type="text" inputmode="text" autocomplete="off" autocapitalize="none" spellcheck="false"></div>
    <p><button onclick="addContact()">Add contact</button></p></div>
   ${selected?`<div class="card"><h3>Chat</h3>
    ${conv.map(m=>`<div class="msg ${m.mine?'mine':'theirs'}">${esc(m.text)}<div class="small">${new Date(m.time*1000).toLocaleTimeString()} ${m.st?('· '+esc(m.st)):''}</div></div>`).join('') || '<p class="small">No messages yet.</p>'}
    <div class="row"><input id="msg" placeholder="message…" type="text" inputmode="text" autocomplete="off" spellcheck="false">
    <button onclick="sendMsg()">Send</button></div></div>`:''}`;
  restoreInputs(cap);
}

function copyEl(id, btn){
  const el=document.getElementById(id);
  if(!el) return;
  el.focus(); el.select();
  const done=()=>{ if(btn){ const o=btn.textContent; btn.textContent='Copied ✓';
    setTimeout(()=>{ btn.textContent=o; },1500); } };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(el.value).then(done).catch(()=>{
      if(document.execCommand('copy')) done(); else showErr('Copy failed — long-press the field to select and copy by hand.');
    });
  } else if(document.execCommand('copy')) done();
  else showErr('Copy failed — long-press the field to select and copy by hand.');
}

async function autoCreate(){
  clearErr(); setBusy(true, 'Creating your account…');
  const r = await api('/api/autocreate', {});
  setBusy(false);
  if(r.error) showErr('Could not create your account: '+r.error);
  await refresh();
}
async function login(){
  const w1=document.getElementById('w1').value, w2=document.getElementById('w2').value;
  if(!w1.trim() || !w2.trim()){
    showErr('Type both words — or tap "Create account" above, no typing needed.');
    return;
  }
  clearErr(); setBusy(true, 'Logging in… this can take up to a minute');
  const r = await api('/api/login', {word1:w1, word2:w2});
  setBusy(false);
  if(r.error) showErr('Login failed: '+r.error);
  await refresh();
}
async function logout(){
  clearErr();
  const r = await api('/api/logout', {});
  if(r && r.error) showErr('Logout failed: '+r.error);
  selected=null; await refresh();
}
async function syncNow(){
  const r = await api('/api/sync', {});
  if(r && r.error) showErr('Sync failed: '+r.error);
  setTimeout(refresh, 800);
}
function sel(id){ selected=id; render(true); }
async function addContact(){
  const id=document.getElementById('cid').value, name=document.getElementById('cname').value;
  const r = await api('/api/contacts', {id:id, name:name});
  if(r.error) showErr('Could not add contact: '+r.error);
  else { clearErr(); selected=id.trim().toLowerCase(); }
  await refresh();
}
async function sendMsg(){
  const el=document.getElementById('msg');
  const m=el.value;
  const r = await api('/api/send', {to:selected, content:m});
  if(r.error) showErr('Could not send: '+r.error);
  else { clearErr(); el.value=''; }
  setTimeout(refresh, 800);
}
refresh(); pollHealth();
setInterval(refresh, 2500);
setInterval(pollHealth, 2000);
</script>
"""


def run_web(port):
    from http.server import ThreadingHTTPServer
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    ensure_postoffice()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler())
    print(f"[app] Nature-Mirror Mesh app on http://127.0.0.1:{port}",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "backend":
        sys.exit(run_backend(sys.argv[1:]))
    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = int(os.environ.get("NMM_PORT", DEFAULT_PORT))
    sys.exit(run_web(port))
