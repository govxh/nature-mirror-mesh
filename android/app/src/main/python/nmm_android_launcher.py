#!/usr/bin/env python3
"""
Nature-Mirror Mesh — Android launcher (Chaquopy glue, NOT core logic).

The core modules in the repo's app/ directory (nmm_app.py, postoffice.py)
are written for the VM/Termux path: they derive their data directory
from their own file location (``<dir of .py>/data/...``), which is fine
on a filesystem you control. Inside an APK that location is Chaquopy's
extraction area, which may be wiped on app upgrade — so on Android this
launcher points the core modules at a stable, app-private tree instead:

    <filesDir>/nmm/postoffice/   post office identity, config, spool
    <filesDir>/nmm/users/        per-account identity + storage
    <filesDir>/nmm/rns_client/   the signed-in backend's RNS config
    <filesDir>/nmm/sessions/     web <-> backend session files

(filesDir is passed in from Java: Context.getFilesDir(). Each Android
process — the main app process and the ":postoffice" service process —
runs its own Chaquopy interpreter and calls one function here.)

Nothing here reimplements the core: postoffice is configured purely by
rebinding the module-level path globals it already reads at runtime
(DATA_DIR / PO_DIR / PN_FILE / PN_PORT in postoffice.py), and nmm_app is
started through its own main()/__main__ entry. The propagation-node
handshake file (propagation_node.txt) therefore lands exactly where
the app expects it: <root>/postoffice/propagation_node.txt.

Both entry points BLOCK for the life of their server (the core modules
run their own loops); Java calls them on worker threads.
"""

import os
import sys
import threading

PN_PORT = "4429"   # must match postoffice.py's NMM_PN_PORT default
UI_PORT = "8899"   # the web UI the WebView loads (MainActivity.UI_URL)


def _log(msg):
    print(f"[nmm-android] {msg}", flush=True)


def _prepare_env(files_dir):
    # postoffice.py reads NMM_PN_PORT once, at import time; set it before
    # anything imports the core modules. setdefault: an explicit value
    # from the environment always wins.
    os.environ.setdefault("NMM_PN_PORT", PN_PORT)
    os.environ.setdefault("NMM_UI_PORT", UI_PORT)
    os.environ.setdefault("NMM_FILES_DIR", files_dir)
    os.environ.setdefault("NMM_DATA_ROOT", _data_root(files_dir))


def _data_root(files_dir):
    return os.path.join(files_dir, "nmm")


def _signal_thread_safe():
    """Let core modules install signal handlers from a worker thread.

    Java starts Python on a worker thread (the process main thread must
    stay free for Android). signal.signal() raises ValueError outside
    the interpreter's main thread; the core modules install SIGTERM /
    SIGINT handlers as part of their normal startup (postoffice.py does).
    Replace signal.signal in THIS process with a tolerant wrapper that
    keeps the handler registration when possible and quietly skips it
    when the platform forbids it. Android stops services by killing the
    process, so a skipped SIGTERM handler changes nothing in practice.
    """
    if threading.current_thread() is threading.main_thread():
        return
    import signal

    original = signal.signal

    def tolerant(signum, handler):
        try:
            return original(signum, handler)
        except (ValueError, OSError):
            return None

    signal.signal = tolerant


# ----------------------------------------------------------------------
# Post office process  (Android ":postoffice" process)
# ----------------------------------------------------------------------

def start_postoffice(files_dir):
    """Entry point called by PostOfficeService (blocks forever)."""
    _prepare_env(files_dir)
    _signal_thread_safe()

    root = _data_root(files_dir)
    po_dir = os.path.join(root, "postoffice")
    os.makedirs(po_dir, exist_ok=True)

    import postoffice

    # Rebind the path globals postoffice.main() reads, so the node's
    # identity/config/spool live under filesDir instead of next to the
    # extracted .py file. Same layout as the VM: <root>/postoffice/.
    postoffice.DATA_DIR = root
    postoffice.PO_DIR = po_dir
    postoffice.PN_FILE = os.path.join(po_dir, "propagation_node.txt")
    postoffice.PN_PORT = int(os.environ["NMM_PN_PORT"])

    _log(f"starting post office: data={po_dir} port={postoffice.PN_PORT}")
    return postoffice.main()


# ----------------------------------------------------------------------
# App process  (main Android process)
# ----------------------------------------------------------------------

def start_app(files_dir):
    """Entry point called by MainActivity (blocks for the server's life).

    Runs nmm_app's web frontend (run_web) in this process. Two pieces of
    Android wiring happen first:

    * Every path global nmm_app derived from DATA_DIR at import time is
      rebound onto <filesDir>/nmm, so accounts, sessions and the RNS
      client config live in stable app-private storage, and the
      propagation-node file is the one the post office process writes:
      <root>/postoffice/propagation_node.txt.
    * A postoffice.pid file containing THIS process's pid is written.
      On the VM, nmm.sh starts the post office and records its pid;
      here the post office is already running in the ":postoffice"
      Android process (started by PostOfficeService before us), and the
      pidfile is how nmm_app's ensure_postoffice() checks liveness —
      a live pid in the file correctly tells it "already running, do
      not spawn one" (its subprocess spawn cannot work inside an APK).
    """
    _prepare_env(files_dir)
    _signal_thread_safe()

    root = _data_root(files_dir)
    po_dir = os.path.join(root, "postoffice")
    os.makedirs(po_dir, exist_ok=True)

    try:
        import nmm_app
    except ImportError as e:
        # app/nmm_app.py is copied in at build time (see app/build.gradle
        # task copyPythonCore). If it was absent, fail loudly in logcat
        # rather than serving a half-dead UI.
        _log(f"FATAL: core module nmm_app is not available: {e}")
        raise

    # Rebind every global that nmm_app computed from DATA_DIR at import
    # time (they are plain module globals, read at runtime).
    derived = {
        "DATA_DIR": root,
        "PO_DIR": po_dir,
        "PN_FILE": os.path.join(po_dir, "propagation_node.txt"),
        "PO_PIDFILE": os.path.join(root, "postoffice.pid"),
        "CLIENT_RNS_DIR": os.path.join(root, "rns_client"),
        "USERS_DIR": os.path.join(root, "users"),
        "SESSIONS_DIR": os.path.join(root, "sessions"),
    }
    for name, path in derived.items():
        if hasattr(nmm_app, name):
            setattr(nmm_app, name, path)
    _log(f"nmm_app data root -> {root}")

    # "Post office already running" marker for ensure_postoffice()
    # (see docstring). The real node lives in the :postoffice process.
    try:
        with open(derived["PO_PIDFILE"], "w") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        _log(f"WARNING: could not write postoffice pidfile: {e}")

    port = int(os.environ.get("NMM_UI_PORT", UI_PORT))
    _log(f"starting nmm_app web UI on 127.0.0.1:{port}")
    if hasattr(nmm_app, "run_web"):
        return nmm_app.run_web(port)
    if hasattr(nmm_app, "main"):
        sys.argv = ["nmm_app.py", str(port)]
        try:
            return nmm_app.main()
        except TypeError:
            return nmm_app.main(sys.argv)
    sys.argv = ["nmm_app.py", str(port)]
    import runpy
    runpy.run_module("nmm_app", run_name="__main__")
    return 0
