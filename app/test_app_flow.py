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

The flow runs TWICE:

  * Run 1 — default mode: nmm_app.py spawns one backend subprocess
    per login (the VM/Termux path). Log: app/test_app_flow.log.
  * Run 2 — thread mode: the app process is started with
    NMM_THREAD_BACKEND=1, so each per-login backend runs on a thread
    inside the web process instead of a subprocess. This is the
    Android/Chaquopy path — inside an APK there is no standalone
    Python executable (no sys.executable) to spawn. The post office
    stays a separate process in both runs (on Android it is the
    ":postoffice" app process). Log: app/test_app_flow_thread.log.

PRE-REGISTERED PASS CRITERION (stated before the runs):
  PASS = in EACH of the two modes:
         (i)   re-login with the same 2 words reproduces the SAME ID
               for both accounts;
         (ii)  account 1 receives account 2's exact message content
               after having been offline while it was sent;
         (iii) account 2 receives the exact reply.
  Additionally each send must reach status "stored at post office"
  at the sender, and account 1's local inbox file must NOT contain
  the token before step 4 (proof the message really waited at the
  post office, not on the "device").

Outputs: app/test_app_flow.log, app/test_app_flow_thread.log and
lab/results/APP_TEST.md.
Exit code 0 = PASS (both modes), 1 = FAIL.
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
                verdicts.get("iii") and verdicts.get("stored", True))


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
        log(f"RUN RESULT ({mode_label}): "
            f"{'PASS' if flow_passed(verdicts) else 'FAIL'}")
        return {"mode": mode_label, "stamp": stamp,
                "verdicts": dict(verdicts), "steps": list(STEPS),
                "log": list(LOG), "msg1": msg1, "msg2": msg2,
                "token1": token1, "token2": token2,
                "passed": flow_passed(verdicts)}

    log("=== Nature-Mirror Mesh — app acceptance test ===")
    log(f"Mode: {mode_label}")
    log(f"Run stamp: {stamp}")
    log("PASS criterion (pre-registered): (i) same words → same ID on "
        "re-login, for both accounts; (ii) account 1 receives account "
        "2's exact message after being offline; (iii) account 2 "
        "receives the exact reply — in EACH of the subprocess and "
        "thread modes. Sends must reach 'stored at post office'; "
        "account 1's local inbox must not contain the token before "
        "step 4.")

    if not wait_ports_free(30):
        step(0, "ports free from a previous run", False,
             "8899/4429 still bound")
        return collect()

    # Hermetic start: wipe app data (test harness only — a real user's
    # data directory is of course never wiped by the app itself).
    if os.path.isdir(DATA_DIR):
        shutil.rmtree(DATA_DIR)
        log("Wiped previous app/data for a hermetic test run.")

    procs = []
    po_log = open(os.path.join(APP_DIR, "test_postoffice.stdout"), "wb")
    app_log = open(os.path.join(APP_DIR, "test_app.stdout"), "wb")
    try:
        # --- start post office -------------------------------------
        po = subprocess.Popen([sys.executable,
                               os.path.join(APP_DIR, "postoffice.py")],
                              stdout=po_log, stderr=subprocess.STDOUT)
        procs.append(("postoffice", po))

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
            return collect()
        with open(os.path.join(DATA_DIR, "postoffice",
                               "propagation_node.txt")) as f:
            pn_hash = f.read().strip()
        log(f"Post office up. Propagation node ID: {pn_hash}")

        # Record the post office pid exactly like the real launchers
        # do (nmm.sh; the Android launcher plants the same file).
        # Without this, the app's ensure_postoffice() would spawn a
        # duplicate post office that fights ours for the port.
        with open(os.path.join(DATA_DIR, "postoffice.pid"), "w") as f:
            f.write(str(po.pid))

        # --- start app ----------------------------------------------
        # Scrub first: the mode must come from app_env alone, never
        # from the ambient environment (an inherited
        # NMM_THREAD_BACKEND would silently turn run 1 into a second
        # thread-mode run).
        env = dict(os.environ)
        env.pop("NMM_THREAD_BACKEND", None)
        env.update(app_env)
        app = subprocess.Popen([sys.executable,
                                os.path.join(APP_DIR, "nmm_app.py"),
                                str(PORT)],
                               stdout=app_log, stderr=subprocess.STDOUT,
                               env=env)
        procs.append(("app", app))

        def app_ready():
            try:
                code, _ = api("GET", "/api/state", timeout=5)
                return code == 200
            except Exception:
                return False

        if not wait_for(app_ready, 60, "app HTTP ready"):
            step(0, "app starts", False, "no HTTP response")
            return collect()

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
        for name, p in procs:
            try:
                p.terminate()
                p.wait(timeout=10)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        po_log.close()
        app_log.close()


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
        "",
        f"Run verdict: **{'PASS' if res['passed'] else 'FAIL'}**",
        "",
    ]
    return lines


def build_md(sub, thr):
    passed = sub["passed"] and thr["passed"]
    lines = [
        "# App Acceptance Test — Nature-Mirror Mesh tiny app (v1)",
        "",
        f"Date (UTC): {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}",
        "",
        "The user's own 5-step acceptance flow, executed against the",
        "real app processes (postoffice.py + nmm_app.py) over their",
        "HTTP endpoints — TWICE, once per backend mode:",
        "",
        "- **Subprocess mode** (default): one backend process per",
        "  login, spawned via sys.executable — the VM/Termux path.",
        "  Full log: `app/test_app_flow.log`.",
        "- **Thread mode** (`NMM_THREAD_BACKEND=1`): the per-login",
        "  backend runs on a daemon thread inside the web process —",
        "  the Android/Chaquopy path, where an APK contains no",
        "  standalone Python executable to spawn. The post office",
        "  remains a separate process in both runs. Full log:",
        "  `app/test_app_flow_thread.log`.",
        "",
        "## Pre-registered criteria",
        "",
        "PASS requires, in EACH of the two modes:",
        "",
        "- (i) same 2 words → same ID on re-login (both accounts);",
        "- (ii) account 1 receives account 2's exact message after",
        "  being offline while it was sent;",
        "- (iii) account 2 receives the exact reply;",
        "- each send reaches status “stored at post office” at the",
        "  sender, and account 1's local inbox file does not contain",
        "  the token before step 4.",
        "",
    ]
    lines += md_run_section("Run 1 — default subprocess mode", sub)
    lines += md_run_section("Run 2 — thread mode "
                            "(NMM_THREAD_BACKEND=1)", thr)
    lines += [
        f"## Verdict: {'PASS' if passed else 'FAIL'}"
        + (" — both modes" if passed else ""),
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
        "on the VM only — in-APK behaviour on a real Android device",
        "remains unverified until a device run. The 2-word key is a",
        "testing convenience and is cryptographically weak by design",
        "at this stage (documented in app/README.md).",
        "",
    ]
    with open(RESULTS_MD, "w") as f:
        f.write("\n".join(lines))


def main():
    sub = run_flow("subprocess mode (default)", {})
    thr = run_flow("thread mode (NMM_THREAD_BACKEND=1)",
                   {"NMM_THREAD_BACKEND": "1"})
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(sub["log"]) + "\n")
    with open(THREAD_LOG_FILE, "w") as f:
        f.write("\n".join(thr["log"]) + "\n")
    build_md(sub, thr)
    passed = sub["passed"] and thr["passed"]
    print("")
    print(f"SUBPROCESS MODE: {'PASS' if sub['passed'] else 'FAIL'} "
          f"(stamp {sub['stamp']})")
    print(f"THREAD MODE:     {'PASS' if thr['passed'] else 'FAIL'} "
          f"(stamp {thr['stamp']})")
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
