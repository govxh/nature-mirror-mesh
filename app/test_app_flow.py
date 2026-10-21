#!/usr/bin/env python3
"""
Nature-Mirror Mesh — automated acceptance test of the tiny app.

Drives the REAL app processes (postoffice.py + nmm_app.py) through
their HTTP endpoints and replicates the user's own acceptance flow,
step for step:

  1. Create account 1 from the 2 words "apple river" → note its ID.
  2. Clear data (logout), create account 2 from "tiger moon"
     → a different ID.
  3. In account 2, add account 1 as a contact by ID and send a message
     containing a unique token.
  4. Clear data, log back into account 1 with only its 2 words → the
     SAME ID must come back, and account 2's message must be waiting
     (it sat in the post office spool while account 1 was gone).
  5. Reply from account 1 to account 2; log back into account 2 with
     its 2 words → the reply must be there.

The MANUAL flow above runs TWICE:

  * Run 1 — default mode: nmm_app.py spawns one backend subprocess
    per login (the VM/Termux path). Log: app/test_app_flow.log.
  * Run 2 — thread mode: the app process is started with
    NMM_THREAD_BACKEND=1, so each per-login backend runs on a thread
    inside the web process instead of a subprocess. This is the
    Android/Chaquopy path — inside an APK there is no standalone
    Python executable (no sys.executable) to spawn. The post office
    stays a separate process in both runs (on Android it is the
    ":postoffice" app process). Log: app/test_app_flow_thread.log.

v0.1.2 adds the AUTO flow (runs 3 and 4, same two modes; logs
app/test_app_flow_auto.log and app/test_app_flow_auto_thread.log) —
the one-tap account creation the user asked for after the first
device test:

  A0. GET /api/health → app up, post office connected.
  A1. POST /api/autocreate (NO words sent) → the app generates 2
      words and logs in; the returned ID must equal the deterministic
      ID of the returned words, and /api/state must show the same
      words + ID (the "Your account" panel data).
  A2. Log out, log in MANUALLY with the generated words → same ID.
  A3. Log out, auto-create a SECOND account → a different ID.
  A4. Account 2 sends to account 1 (offline) → "stored at post
      office", token absent from account 1's local inbox.
  A5. Manual login with account 1's generated words → same ID, and
      the waiting message is there.
  A6. Reply; manual login with account 2's generated words → the
      reply is there.

Both manual runs also execute the UI regression test
(app/test_ui_dom.js, needs node): the REAL served page's script
runs in a stub DOM and must prove that poll ticks never rebuild the
page over in-progress typing (the v0.1.1 device bug: the 2.5 s
innerHTML rebuild erasing the login word fields). The same test
FAILS against the v0.1.1 page and must PASS against this one.

PRE-REGISTERED PASS CRITERIA (stated before the runs):
  Manual flow, in EACH of the two modes:
         (i)   re-login with the same 2 words reproduces the SAME ID
               for both accounts;
         (ii)  account 1 receives account 2's exact message content
               after having been offline while it was sent;
         (iii) account 2 receives the exact reply;
         (ui)  the UI regression test passes.
  Additionally each send must reach status "stored at post office"
  at the sender, and account 1's local inbox file must NOT contain
  the token before step 4 (proof the message really waited at the
  post office, not on the "device").
  Auto flow, in EACH of the two modes:
         (gen)     auto-create returns 2 words whose deterministic
                   ID is the logged-in ID, and state shows them;
         (relogin) manual login with the generated words reproduces
                   the same ID;
         (deliver) offline post-office delivery between two
                   auto-created accounts;
         (reply)   the reply is delivered.

Outputs: app/test_app_flow.log, app/test_app_flow_thread.log,
app/test_app_flow_auto.log, app/test_app_flow_auto_thread.log and
lab/results/APP_TEST.md.
Exit code 0 = PASS (all four runs), 1 = FAIL.
"""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)
DATA_DIR = os.path.join(APP_DIR, "data")
RESULTS_MD = os.path.join(PROJECT_DIR, "lab", "results", "APP_TEST.md")
LOG_FILE = os.path.join(APP_DIR, "test_app_flow.log")
THREAD_LOG_FILE = os.path.join(APP_DIR, "test_app_flow_thread.log")
AUTO_LOG_FILE = os.path.join(APP_DIR, "test_app_flow_auto.log")
AUTO_THREAD_LOG_FILE = os.path.join(APP_DIR,
                                   "test_app_flow_auto_thread.log")
UI_DOM_JS = os.path.join(APP_DIR, "test_ui_dom.js")
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

WORDS_1 = ("apple", "river")
WORDS_2 = ("tiger", "moon")

LOG = []
STEPS = []  # (step, description, ok, evidence)


def log(msg=""):
    line = str(msg)
    print(line, flush=True)
    LOG.append(line)


def step(num, desc, ok, evidence):
    STEPS.append((num, desc, ok, evidence))
    log(f"STEP {num} {'OK ' if ok else 'FAIL'} — {desc}")
    log(f"        evidence: {evidence}")


def api(method, path, payload=None, timeout=120):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def wait_for(predicate, timeout, desc, interval=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    log(f"TIMEOUT waiting for: {desc}")
    return False


def wait_ports_free(timeout=30):
    """Between runs: the previous run's post office (4429) and app
    (8899) must have released their ports before the next run binds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        free = True
        for port in (PORT, 4429):
            try:
                s = socket.create_connection(("127.0.0.1", port), 0.5)
                s.close()
                free = False
            except Exception:
                pass
        if free:
            return True
        time.sleep(0.5)
    return False


def expected_id(words):
    import RNS
    seed = hashlib.sha512(" ".join(words).encode()).digest()
    identity = RNS.Identity.from_bytes(seed)
    return RNS.hexrep(RNS.Destination.hash(identity, "lxmf", "delivery"),
                      delimit=False)


def inbox_contains(user_id, token):
    path = os.path.join(DATA_DIR, "users", user_id, "inbox.json")
    if not os.path.isfile(path):
        return False
    with open(path) as f:
        return token in f.read()


def sent_status(local_id):
    _, state = api("GET", "/api/state")
    for entry in state.get("sent", []):
        if entry["local_id"] == local_id:
            return entry["status"]
    return None


def state_inbox_has(content, from_id=None):
    _, state = api("GET", "/api/state")
    for m in state.get("inbox", []):
        if m["content"] == content and \
                (from_id is None or m["from"] == from_id):
            return True
    return False


def flow_passed(verdicts):
    return bool(verdicts.get("i") and verdicts.get("ii") and
                verdicts.get("iii") and verdicts.get("stored", True)
                and verdicts.get("ui", True))


def auto_flow_passed(verdicts):
    return bool(verdicts.get("gen") and verdicts.get("relogin") and
                verdicts.get("deliver") and verdicts.get("reply") and
                verdicts.get("stored", True))


def boot_stack(app_env):
    """Start the post office + app exactly as the flows always have
    (hermetic data wipe, pidfile planted like the real launchers).
    Returns a ctx dict, or None after recording the failed step 0."""
    if not wait_ports_free(30):
        step(0, "ports free from a previous run", False,
             "8899/4429 still bound")
        return None
    if os.path.isdir(DATA_DIR):
        shutil.rmtree(DATA_DIR)
        log("Wiped previous app/data for a hermetic test run.")
    ctx = {"procs": [], "logs": []}
    po_log = open(os.path.join(APP_DIR, "test_postoffice.stdout"), "wb")
    app_log = open(os.path.join(APP_DIR, "test_app.stdout"), "wb")
    ctx["logs"] = [po_log, app_log]

    po = subprocess.Popen([sys.executable,
                           os.path.join(APP_DIR, "postoffice.py")],
                          stdout=po_log, stderr=subprocess.STDOUT)
    ctx["procs"].append(("postoffice", po))

    def po_ready():
        if not os.path.isfile(os.path.join(
                DATA_DIR, "postoffice", "propagation_node.txt")):
            return False
        try:
            s = socket.create_connection(("127.0.0.1", 4429), 1)
            s.close()
            return True
        except Exception:
            return False

    if not wait_for(po_ready, 60, "post office ready"):
        step(0, "post office starts", False, "no PN file / port")
        shutdown_stack(ctx)
        return None
    with open(os.path.join(DATA_DIR, "postoffice",
                           "propagation_node.txt")) as f:
        pn_hash = f.read().strip()
    log(f"Post office up. Propagation node ID: {pn_hash}")

    # Record the post office pid exactly like the real launchers do
    # (nmm.sh; the Android launcher plants the same file). Without
    # this, the app's ensure_postoffice() would spawn a duplicate
    # post office that fights ours for the port.
    with open(os.path.join(DATA_DIR, "postoffice.pid"), "w") as f:
        f.write(str(po.pid))

    # Scrub first: the mode must come from app_env alone, never from
    # the ambient environment (an inherited NMM_THREAD_BACKEND would
    # silently turn a subprocess run into a second thread-mode run).
    env = dict(os.environ)
    env.pop("NMM_THREAD_BACKEND", None)
    env.update(app_env)
    app = subprocess.Popen([sys.executable,
                            os.path.join(APP_DIR, "nmm_app.py"),
                            str(PORT)],
                           stdout=app_log, stderr=subprocess.STDOUT,
                           env=env)
    ctx["procs"].append(("app", app))

    def app_ready():
        try:
            code, _ = api("GET", "/api/state", timeout=5)
            return code == 200
        except Exception:
            return False

    if not wait_for(app_ready, 60, "app HTTP ready"):
        step(0, "app starts", False, "no HTTP response")
        shutdown_stack(ctx)
        return None
    return ctx


def shutdown_stack(ctx):
    if not ctx:
        return
    for name, p in ctx.get("procs", []):
        try:
            p.terminate()
            p.wait(timeout=10)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    for f in ctx.get("logs", []):
        try:
            f.close()
        except Exception:
            pass


def ui_regression_checks():
    """The typing-preservation regression test against the REAL page
    served by the running app. Two layers:
    (1) structural assertions on the served script — the state-change
        guard, capture/restore and typing-guard code paths must be
        present (and the guards must appear in render() BEFORE the
        first innerHTML rebuild);
    (2) functional: run the page's own script in a stub DOM under
        node (app/test_ui_dom.js) and simulate typing through poll
        ticks. Skipped (not failed) only if node is unavailable.
    Returns (ok, evidence)."""
    try:
        with urllib.request.urlopen(BASE + "/", timeout=10) as r:
            page = r.read().decode()
    except Exception as e:
        return False, f"could not fetch the served page: {e}"
    snap = os.path.join(APP_DIR, "test_page_snapshot.html")
    with open(snap, "w") as f:
        f.write(page)
    tokens = ["captureInputs", "restoreInputs", "stateSig",
              "userIsTyping", "sig===lastSig", "/api/autocreate",
              "/api/health", "showErr", "navigator.clipboard",
              "execCommand('copy')", 'inputmode="text"',
              'id="aw1"', 'id="aw2"', 'id="aid"']
    missing = [t for t in tokens if t not in page]
    if missing:
        return False, f"served page is missing code paths: {missing}"
    seg_start = page.index("function render(")
    seg_end = page.index("function copyEl", seg_start)
    seg = page[seg_start:seg_end]
    guard_at = seg.find("userIsTyping()")
    rebuild_at = seg.find("innerHTML")
    cap_at = seg.find("captureInputs()")
    if not (0 <= guard_at < rebuild_at and 0 <= cap_at < rebuild_at):
        return False, ("render() does not guard/capture before its "
                       "first innerHTML rebuild")
    node = shutil.which("node")
    if not node:
        return True, ("structural assertions passed (14 tokens + "
                      "guard-before-rebuild); node unavailable, DOM "
                      "simulation skipped")
    proc = subprocess.run([node, UI_DOM_JS, snap],
                          capture_output=True, text=True, timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = "; ".join(line for line in out.splitlines() if line.strip())
    if proc.returncode == 0 and "UI-DOM: PASS" in out:
        return True, f"structural assertions passed; DOM simulation: {tail}"
    return False, f"DOM simulation failed: {tail}"


def run_flow(mode_label, app_env):
    """One full pass of the user's 5-step flow. app_env is merged
    into the environment of the app process ({} = default subprocess
    mode; {"NMM_THREAD_BACKEND": "1"} = thread mode). Returns a
    result dict with verdicts, steps, log lines and the messages."""
    LOG.clear()
    STEPS.clear()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    token1 = f"NMM-APPTEST-{stamp}-ONE"
    token2 = f"NMM-APPTEST-{stamp}-TWO"
    msg1 = f"Assalam-o-Alaikum account 1, this waited at the post office: {token1}"
    msg2 = f"Wa-Alaikum-Assalam account 2, reply from account 1: {token2}"
    verdicts = {}

    def collect():
        log("")
        log(f"CRITERION (i)   same words → same ID:      {verdicts.get('i')}")
        log(f"CRITERION (ii)  offline message delivered: {verdicts.get('ii')}")
        log(f"CRITERION (iii) reply delivered:           {verdicts.get('iii')}")
        log(f"CRITERION (ui)  typing-preservation page:  {verdicts.get('ui')}")
        log(f"RUN RESULT ({mode_label}): "
            f"{'PASS' if flow_passed(verdicts) else 'FAIL'}")
        return {"mode": mode_label, "stamp": stamp,
                "verdicts": dict(verdicts), "steps": list(STEPS),
                "log": list(LOG), "msg1": msg1, "msg2": msg2,
                "token1": token1, "token2": token2,
                "passed": flow_passed(verdicts)}

    log("=== Nature-Mirror Mesh — app acceptance test (manual flow) ===")
    log(f"Mode: {mode_label}")
    log(f"Run stamp: {stamp}")
    log("PASS criterion (pre-registered): (i) same words → same ID on "
        "re-login, for both accounts; (ii) account 1 receives account "
        "2's exact message after being offline; (iii) account 2 "
        "receives the exact reply — in EACH of the subprocess and "
        "thread modes. Sends must reach 'stored at post office'; "
        "account 1's local inbox must not contain the token before "
        "step 4. Plus (ui): the served page must pass the "
        "typing-preservation DOM regression test.")

    ctx = boot_stack(app_env)
    if ctx is None:
        return collect()
    try:
        # --- UI regression test against the served page -------------
        ui_ok, ui_ev = ui_regression_checks()
        verdicts["ui"] = ui_ok
        step("U", "served page: typing never wiped by re-render "
                  "(DOM regression test)", ui_ok, ui_ev)

        exp1 = expected_id(WORDS_1)
        exp2 = expected_id(WORDS_2)
        log(f"Expected ID for {WORDS_1}: {exp1}")
        log(f"Expected ID for {WORDS_2}: {exp2}")

        # --- STEP 1: create account 1 --------------------------------
        code, r = api("POST", "/api/login",
                      {"word1": WORDS_1[0], "word2": WORDS_1[1]})
        id1 = r.get("id")
        step(1, "create account 1 ('apple river')",
             code == 200 and id1 == exp1,
             f"http={code} id={id1} (deterministic expectation {exp1})")

        # --- STEP 2: clear data, create account 2 ---------------------
        api("POST", "/api/logout", {})
        _, st = api("GET", "/api/state")
        logged_out = not st.get("logged_in")
        code, r = api("POST", "/api/login",
                      {"word1": WORDS_2[0], "word2": WORDS_2[1]})
        id2 = r.get("id")
        step(2, "clear data → account 2 ('tiger moon'), different ID",
             logged_out and code == 200 and id2 == exp2 and id2 != id1,
             f"logged_out={logged_out} http={code} id={id2}")

        # --- STEP 3: account 2 sends to account 1 ----------------------
        code, r = api("POST", "/api/contacts",
                      {"id": id1, "name": "Account 1"})
        code, r = api("POST", "/api/send",
                      {"to": id1, "content": msg1})
        local_id = r.get("local_id")
        ok_stored = wait_for(
            lambda: sent_status(local_id) == "stored at post office",
            300, "message status 'stored at post office'")
        spool_dir = os.path.join(DATA_DIR, "postoffice", "storage",
                                 "lxmf", "messagestore")
        spool_files = (len(os.listdir(spool_dir))
                       if os.path.isdir(spool_dir) else 0)
        not_local = not inbox_contains(id1, token1)
        step(3, "account 2 sends to account 1's ID; message stored at "
                "post office",
             bool(local_id) and ok_stored and not_local,
             f"local_id={local_id} status={sent_status(local_id)!r} "
             f"spool_files={spool_files} "
             f"token_in_acct1_local_inbox={not not_local}")
        verdicts["stored"] = ok_stored

        # --- STEP 4: back to account 1 with only its 2 words ----------
        api("POST", "/api/logout", {})
        code, r = api("POST", "/api/login",
                      {"word1": WORDS_1[0], "word2": WORDS_1[1]})
        id1b = r.get("id")
        same_id = (id1b == id1)
        step("4a", "re-login account 1 with only its 2 words → same ID",
             code == 200 and same_id,
             f"http={code} id={id1b} (original {id1})")
        verdicts["i"] = same_id

        got = wait_for(lambda: state_inbox_has(msg1, from_id=id2),
                       180, "account 1 inbox receives waiting message")
        step("4b", "account 1 receives account 2's exact message",
             got, f"content match={got} token={token1}")
        verdicts["ii"] = got

        # --- STEP 5: reply, back to account 2 --------------------------
        code, r = api("POST", "/api/contacts",
                      {"id": id2, "name": "Account 2"})
        code, r = api("POST", "/api/send",
                      {"to": id2, "content": msg2})
        reply_local = r.get("local_id")
        ok_reply_stored = wait_for(
            lambda: sent_status(reply_local) == "stored at post office",
            300, "reply status 'stored at post office'")
        reply_status_seen = sent_status(reply_local)
        api("POST", "/api/logout", {})
        code, r = api("POST", "/api/login",
                      {"word1": WORDS_2[0], "word2": WORDS_2[1]})
        id2b = r.get("id")
        got_reply = wait_for(lambda: state_inbox_has(msg2, from_id=id1),
                             180, "account 2 inbox receives reply")
        step(5, "account 1 replies; account 2 (re-login, same ID) "
                "receives the exact reply",
             ok_reply_stored and id2b == id2 and got_reply,
             f"reply_status={reply_status_seen!r} "
             f"id2_again={id2b} (same={id2b == id2}) "
             f"reply_received={got_reply} token={token2}")
        verdicts["i"] = verdicts.get("i") and (id2b == id2)
        verdicts["iii"] = got_reply

        api("POST", "/api/logout", {})
        return collect()
    finally:
        shutdown_stack(ctx)


def run_auto_flow(mode_label, app_env):
    """The v0.1.2 one-tap flow: accounts created by POST
    /api/autocreate with NO typing, then exercised end to end using
    manual logins with the generated words. Same stack, same post
    office store-and-forward criteria as the manual flow."""
    LOG.clear()
    STEPS.clear()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    token1 = f"NMM-AUTOTEST-{stamp}-ONE"
    token2 = f"NMM-AUTOTEST-{stamp}-TWO"
    msg1 = f"Assalam-o-Alaikum auto account 1, this waited at the post office: {token1}"
    msg2 = f"Wa-Alaikum-Assalam auto account 2, reply from auto account 1: {token2}"
    verdicts = {}

    def collect():
        log("")
        log(f"CRITERION (gen)     auto-create words → ID:  {verdicts.get('gen')}")
        log(f"CRITERION (relogin) generated words log in:  {verdicts.get('relogin')}")
        log(f"CRITERION (deliver) offline delivery:        {verdicts.get('deliver')}")
        log(f"CRITERION (reply)   reply delivered:         {verdicts.get('reply')}")
        log(f"RUN RESULT ({mode_label}, auto): "
            f"{'PASS' if auto_flow_passed(verdicts) else 'FAIL'}")
        return {"mode": mode_label, "stamp": stamp,
                "verdicts": dict(verdicts), "steps": list(STEPS),
                "log": list(LOG), "msg1": msg1, "msg2": msg2,
                "token1": token1, "token2": token2,
                "passed": auto_flow_passed(verdicts)}

    log("=== Nature-Mirror Mesh — app acceptance test (AUTO flow) ===")
    log(f"Mode: {mode_label}")
    log(f"Run stamp: {stamp}")
    log("PASS criterion (pre-registered): (gen) auto-create returns "
        "2 words whose deterministic ID is the session ID and state "
        "shows the same words+ID; (relogin) manual login with the "
        "generated words reproduces the ID; (deliver) offline "
        "post-office delivery between two auto-created accounts; "
        "(reply) the reply is delivered.")

    ctx = boot_stack(app_env)
    if ctx is None:
        return collect()
    try:
        # --- A0: health endpoint ------------------------------------
        code, h = api("GET", "/api/health")
        step("A0", "GET /api/health: app up, post office connected",
             code == 200 and h.get("app") == "up" and
             h.get("postoffice") == "connected" and
             h.get("logged_in") is False,
             f"http={code} health={h}")

        # --- A1: one-tap create, account 1 ---------------------------
        code, r = api("POST", "/api/autocreate", {})
        words1 = (r.get("word1") or "", r.get("word2") or "")
        id_a1 = r.get("id")
        exp_a1 = expected_id(words1) if all(words1) else None
        _, st = api("GET", "/api/state")
        state_words = tuple(st.get("words") or ())
        step("A1", "auto-create account 1 (no typing): words "
                   "generated, ID = deterministic ID of the words, "
                   "state shows words + ID",
             code == 200 and all(words1) and id_a1 == exp_a1 and
             st.get("logged_in") and st.get("id") == id_a1 and
             state_words == words1,
             f"http={code} words={words1} id={id_a1} "
             f"deterministic={exp_a1} state_words={state_words}")
        verdicts["gen"] = bool(code == 200 and id_a1 == exp_a1 and
                                state_words == words1)
        if not id_a1:
            return collect()
        log(f"Auto account 1: words={words1} id={id_a1}")

        # --- A2: logout, manual login with the generated words -------
        api("POST", "/api/logout", {})
        code, r = api("POST", "/api/login",
                      {"word1": words1[0], "word2": words1[1]})
        relogin_same = (code == 200 and r.get("id") == id_a1)
        step("A2", "log out → manual login with the generated words "
                   "→ same ID",
             relogin_same,
             f"http={code} id={r.get('id')} (original {id_a1})")
        verdicts["relogin"] = relogin_same

        # --- A3: auto-create account 2 (must differ) ------------------
        api("POST", "/api/logout", {})
        id_a2 = None
        words2 = None
        tries = []
        for _ in range(3):
            code, r = api("POST", "/api/autocreate", {})
            tries.append(r.get("id"))
            if code == 200 and r.get("id") and r.get("id") != id_a1:
                id_a2 = r["id"]
                words2 = (r.get("word1") or "", r.get("word2") or "")
                break
            api("POST", "/api/logout", {})
        exp_a2 = expected_id(words2) if words2 and all(words2) else None
        step("A3", "auto-create account 2 → different account, ID "
                   "matches its generated words",
             id_a2 is not None and id_a2 == exp_a2,
             f"words={words2} id={id_a2} deterministic={exp_a2} "
             f"tries={tries}")
        verdicts["gen"] = verdicts.get("gen") and \
            bool(id_a2 is not None and id_a2 == exp_a2)
        if not id_a2:
            return collect()
        log(f"Auto account 2: words={words2} id={id_a2}")

        # --- A4: account 2 sends to account 1 (offline) ---------------
        api("POST", "/api/contacts", {"id": id_a1,
                                      "name": "Auto Account 1"})
        code, r = api("POST", "/api/send",
                      {"to": id_a1, "content": msg1})
        local_id = r.get("local_id")
        ok_stored = wait_for(
            lambda: sent_status(local_id) == "stored at post office",
            300, "auto message status 'stored at post office'")
        not_local = not inbox_contains(id_a1, token1)
        step("A4", "account 2 sends to account 1's ID; message "
                   "stored at post office",
             bool(local_id) and ok_stored and not_local,
             f"local_id={local_id} status={sent_status(local_id)!r} "
             f"token_in_acct1_local_inbox={not not_local}")
        verdicts["stored"] = ok_stored

        # --- A5: manual login account 1 → message waiting -------------
        api("POST", "/api/logout", {})
        code, r = api("POST", "/api/login",
                      {"word1": words1[0], "word2": words1[1]})
        back1 = (code == 200 and r.get("id") == id_a1)
        got = wait_for(lambda: state_inbox_has(msg1, from_id=id_a2),
                       180, "auto account 1 inbox receives message")
        step("A5", "manual login with account 1's generated words → "
                   "same ID, waiting message received",
             back1 and got,
             f"http={code} id={r.get('id')} same={back1} "
             f"message_received={got} token={token1}")
        verdicts["relogin"] = verdicts.get("relogin") and back1
        verdicts["deliver"] = got

        # --- A6: reply → account 2 via its generated words ------------
        api("POST", "/api/contacts", {"id": id_a2,
                                      "name": "Auto Account 2"})
        code, r = api("POST", "/api/send",
                      {"to": id_a2, "content": msg2})
        reply_local = r.get("local_id")
        ok_reply_stored = wait_for(
            lambda: sent_status(reply_local) == "stored at post office",
            300, "auto reply status 'stored at post office'")
        reply_status_seen = sent_status(reply_local)
        api("POST", "/api/logout", {})
        code, r = api("POST", "/api/login",
                      {"word1": words2[0], "word2": words2[1]})
        back2 = (code == 200 and r.get("id") == id_a2)
        got_reply = wait_for(
            lambda: state_inbox_has(msg2, from_id=id_a1),
            180, "auto account 2 inbox receives reply")
        step("A6", "reply sent; manual login with account 2's "
                   "generated words → same ID, reply received",
             ok_reply_stored and back2 and got_reply,
             f"reply_status={reply_status_seen!r} "
             f"id2_again={r.get('id')} same={back2} "
             f"reply_received={got_reply} token={token2}")
        verdicts["stored"] = verdicts.get("stored", True) and \
            ok_reply_stored
        verdicts["relogin"] = verdicts.get("relogin") and back2
        verdicts["reply"] = got_reply

        api("POST", "/api/logout", {})
        return collect()
    finally:
        shutdown_stack(ctx)


def md_run_section(title, res):
    v = res["verdicts"]
    lines = [
        f"## {title}",
        "",
        f"Run stamp: {res['stamp']}",
        "",
        "| Step | What | Result | Evidence |",
        "|---|---|---|---|",
    ]
    for num, desc, ok, ev in res["steps"]:
        lines.append(f"| {num} | {desc} | {'✅ PASS' if ok else '❌ FAIL'} "
                     f"| {ev} |")
    lines += [
        "",
        f"- (i) same 2 words → same ID on re-login (both accounts): "
        f"**{v.get('i')}**",
        f"- (ii) account 1 receives account 2's exact message after "
        f"being offline: **{v.get('ii')}** — message sent: "
        f"“{res['msg1']}”",
        f"- (iii) account 2 receives the exact reply: "
        f"**{v.get('iii')}** — reply sent: “{res['msg2']}”",
        f"- (ui) typing-preservation DOM regression test: "
        f"**{v.get('ui')}**",
        "",
        f"Run verdict: **{'PASS' if res['passed'] else 'FAIL'}**",
        "",
    ]
    return lines


def md_auto_section(title, res):
    v = res["verdicts"]
    lines = [
        f"## {title}",
        "",
        f"Run stamp: {res['stamp']}",
        "",
        "| Step | What | Result | Evidence |",
        "|---|---|---|---|",
    ]
    for num, desc, ok, ev in res["steps"]:
        lines.append(f"| {num} | {desc} | {'✅ PASS' if ok else '❌ FAIL'} "
                     f"| {ev} |")
    lines += [
        "",
        f"- (gen) auto-create returns 2 words whose deterministic ID "
        f"is the session ID, state shows the same words + ID: "
        f"**{v.get('gen')}**",
        f"- (relogin) manual login with the generated words "
        f"reproduces the same ID: **{v.get('relogin')}**",
        f"- (deliver) account 1 receives account 2's exact message "
        f"after being offline: **{v.get('deliver')}** — message sent: "
        f"“{res['msg1']}”",
        f"- (reply) account 2 receives the exact reply: "
        f"**{v.get('reply')}** — reply sent: “{res['msg2']}”",
        "",
        f"Run verdict: **{'PASS' if res['passed'] else 'FAIL'}**",
        "",
    ]
    return lines


def build_md(sub, thr, asub, athr):
    passed = sub["passed"] and thr["passed"] and \
        asub["passed"] and athr["passed"]
    lines = [
        "# App Acceptance Test — Nature-Mirror Mesh tiny app",
        "",
        f"Date (UTC): {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}",
        "",
        "## v0.1.2 — what changed and why",
        "",
        "v0.1.1 reached a real phone and the user reported: “it",
        "doesn't let me write anything” — the login screen showed two",
        "empty word fields and typing into them failed.",
        "",
        "**Root cause (confirmed by the user's on-device report and",
        "by code inspection):** the page ran `refresh()` on a 2.5 s",
        "interval and `render()` rebuilt the whole `#app` innerHTML",
        "on every tick, erasing in-progress typing — the user typed",
        "word 1, the tick fired, word 1 vanished before word 2.",
        "Secondary risks fixed at the same time: the WebView was not",
        "explicitly focusable-in-touch-mode (some devices then never",
        "raise the keyboard for page inputs), and every API failure",
        "was silent (a dead “Loading…” screen with no reason shown).",
        "",
        "Fixes in v0.1.2:",
        "",
        "- **Re-rendering can no longer destroy typing.** A rebuild",
        "  happens only when the rendered state actually changed",
        "  (signature compare); it never happens while a text field",
        "  is focused, unless the login state itself flipped; and",
        "  when it does happen, every input's value + focus +",
        "  selection are captured first and restored after.",
        "  Regression-tested by executing the real served page in a",
        "  stub DOM (`app/test_ui_dom.js`, step U in runs 1–2): the",
        "  same test FAILS against the v0.1.1 page (typing wiped on",
        "  the first tick) and must PASS here.",
        "- **One-tap account creation.** “Create account” needs no",
        "  typing: the backend generates 2 random words (`secrets`",
        "  over an embedded 256-word list), logs in through the",
        "  exact same identity derivation as manual entry, and the",
        "  “Your account” panel shows the 2 words and the full",
        "  32-hex ID in readonly fields with Copy buttons, plus:",
        "  “Save these 2 words — they are your only key. Anyone",
        "  with them has your account.” Manual 2-word entry stays",
        "  below for returning users.",
        "- **No more silent failures.** Every API call surfaces its",
        "  error in a visible error line; login shows a busy state;",
        "  a status line polls `GET /api/health` (post office",
        "  reachable? backend stage? session state?) built on the",
        "  existing ready.json / status.json IPC.",
        "- **WebView hardening (Android shell):** focusable +",
        "  focusable-in-touch-mode + requestFocus on load, and a",
        "  WebChromeClient. Cleartext config and permissions",
        "  unchanged.",
        "- **Reliability fix found BY these tests** (first suite",
        "  attempt: 2 of 4 runs failed intermittently with “failed:",
        "  ID not found (no path)”): a sender waited for a *live",
        "  path* to the offline recipient, but RNS culls a path-table",
        "  entry the moment the interface it was learned on",
        "  disappears — and an offline contact's only interface is",
        "  its own closed connection (post office log, instrumented",
        "  repro: “Ignoring path request …, no path known” for a",
        "  destination that had announced to it directly). A",
        "  PROPAGATED message never needed that path — only the",
        "  recipient's public key. Now every login publishes its",
        "  public key to an on-device identity directory",
        "  (`data/identities/<id>.pub`) and `do_send` resolves the",
        "  identity from there / RNS recall first; the 240 s",
        "  path-request loop remains only as fallback for IDs never",
        "  seen on this device. Same repro sequence after the fix:",
        "  “stored at post office” in ~8 s.",
        "",
        "## The runs",
        "",
        "Four runs against the real app processes (postoffice.py +",
        "nmm_app.py) over their HTTP endpoints — the user's 5-step",
        "manual flow and the new auto flow, each in both backend",
        "modes:",
        "",
        "- **Subprocess mode** (default): one backend process per",
        "  login, spawned via sys.executable — the VM/Termux path.",
        "- **Thread mode** (`NMM_THREAD_BACKEND=1`): the per-login",
        "  backend runs on a daemon thread inside the web process —",
        "  the Android/Chaquopy path, where an APK contains no",
        "  standalone Python executable to spawn. The post office",
        "  remains a separate process in both runs.",
        "",
        "Full logs: `app/test_app_flow.log`,",
        "`app/test_app_flow_thread.log`, `app/test_app_flow_auto.log`,",
        "`app/test_app_flow_auto_thread.log`. The offline (loopback-",
        "only network namespace) rerun of this suite is reported in",
        "`lab/results/OFFLINE_TEST_V012.md`.",
        "",
        "## Pre-registered criteria",
        "",
        "PASS requires, in EACH mode:",
        "",
        "- Manual: (i) same 2 words → same ID on re-login (both",
        "  accounts); (ii) account 1 receives account 2's exact",
        "  message after being offline while it was sent; (iii)",
        "  account 2 receives the exact reply; (ui) the typing-",
        "  preservation DOM regression test passes; each send",
        "  reaches “stored at post office”, and account 1's local",
        "  inbox file does not contain the token before step 4.",
        "- Auto: (gen) auto-create's words deterministically derive",
        "  the session ID and state shows them; (relogin) manual",
        "  login with the generated words reproduces the ID;",
        "  (deliver) offline delivery between two auto-created",
        "  accounts; (reply) the reply is delivered.",
        "",
    ]
    lines += md_run_section("Run 1 — manual flow, subprocess mode",
                            sub)
    lines += md_run_section("Run 2 — manual flow, thread mode "
                            "(NMM_THREAD_BACKEND=1)", thr)
    lines += md_auto_section("Run 3 — auto flow, subprocess mode",
                             asub)
    lines += md_auto_section("Run 4 — auto flow, thread mode "
                             "(NMM_THREAD_BACKEND=1)", athr)
    lines += [
        f"## Verdict: {'PASS' if passed else 'FAIL'}"
        + (" — all four runs" if passed else ""),
        "",
        "## Honest scope",
        "Single device, loopback TCP only — the post office and both",
        "accounts ran on one machine, exactly like the user's one-phone",
        "test will. No internet, no radio. Thread mode shares one",
        "process-wide Reticulum instance across logins (RNS allows",
        "only one per process) and the backend deregisters its LXMF",
        "destinations (delivery + the router's propagation",
        "destination) at logout so the same account can log in",
        "again; this mirrors the in-APK lifecycle but is verified",
        "on the VM only. v0.1.2's fixes — including the typing fix —",
        "are VM-verified against the real served page and the real",
        "app processes; **the device retest on the user's phone is",
        "still pending** and is the acceptance gate for the UX fix.",
        "The 2-word key (typed or generated) is a testing",
        "convenience and is cryptographically weak by design at",
        "this stage (documented in app/README.md).",
        "",
    ]
    with open(RESULTS_MD, "w") as f:
        f.write("\n".join(lines))


def main():
    sub = run_flow("subprocess mode (default)", {})
    thr = run_flow("thread mode (NMM_THREAD_BACKEND=1)",
                   {"NMM_THREAD_BACKEND": "1"})
    asub = run_auto_flow("subprocess mode (default)", {})
    athr = run_auto_flow("thread mode (NMM_THREAD_BACKEND=1)",
                         {"NMM_THREAD_BACKEND": "1"})
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(sub["log"]) + "\n")
    with open(THREAD_LOG_FILE, "w") as f:
        f.write("\n".join(thr["log"]) + "\n")
    with open(AUTO_LOG_FILE, "w") as f:
        f.write("\n".join(asub["log"]) + "\n")
    with open(AUTO_THREAD_LOG_FILE, "w") as f:
        f.write("\n".join(athr["log"]) + "\n")
    build_md(sub, thr, asub, athr)
    passed = sub["passed"] and thr["passed"] and \
        asub["passed"] and athr["passed"]
    print("")
    print(f"MANUAL / SUBPROCESS: {'PASS' if sub['passed'] else 'FAIL'} "
          f"(stamp {sub['stamp']})")
    print(f"MANUAL / THREAD:     {'PASS' if thr['passed'] else 'FAIL'} "
          f"(stamp {thr['stamp']})")
    print(f"AUTO / SUBPROCESS:   {'PASS' if asub['passed'] else 'FAIL'} "
          f"(stamp {asub['stamp']})")
    print(f"AUTO / THREAD:       {'PASS' if athr['passed'] else 'FAIL'} "
          f"(stamp {athr['stamp']})")
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
