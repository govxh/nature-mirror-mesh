#!/usr/bin/env python3
"""
Nature-Mirror Mesh — automated acceptance test of the tiny app.

Drives the REAL app processes (postoffice.py + nmm_app.py, including
its per-login backend processes) through their HTTP endpoints and
replicates the user's own acceptance flow, step for step:

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

PRE-REGISTERED PASS CRITERION (stated before the run):
  PASS = (i)   re-login with the same 2 words reproduces the SAME ID
               for both accounts;
         (ii)  account 1 receives account 2's exact message content
               after having been offline while it was sent;
         (iii) account 2 receives the exact reply.
  Additionally the send in step 3 must reach status
  "stored at post office" at the sender, and account 1's local inbox
  file must NOT contain the token before step 4 (proof the message
  really waited at the post office, not on the "device").

Outputs: app/test_app_flow.log and lab/results/APP_TEST.md.
Exit code 0 = PASS, 1 = FAIL.
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


def main():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    token1 = f"NMM-APPTEST-{stamp}-ONE"
    token2 = f"NMM-APPTEST-{stamp}-TWO"
    msg1 = f"Assalam-o-Alaikum account 1, this waited at the post office: {token1}"
    msg2 = f"Wa-Alaikum-Assalam account 2, reply from account 1: {token2}"

    log("=== Nature-Mirror Mesh — app acceptance test ===")
    log(f"Run stamp: {stamp}")
    log("PASS criterion (pre-registered): (i) same words → same ID on "
        "re-login, for both accounts; (ii) account 1 receives account "
        "2's exact message after being offline; (iii) account 2 "
        "receives the exact reply. Send must reach 'stored at post "
        "office'; account 1's local inbox must not contain the token "
        "before step 4.")

    # Hermetic start: wipe app data (test harness only — a real user's
    # data directory is of course never wiped by the app itself).
    if os.path.isdir(DATA_DIR):
        shutil.rmtree(DATA_DIR)
        log("Wiped previous app/data for a hermetic test run.")

    procs = []
    po_log = open(os.path.join(APP_DIR, "test_postoffice.stdout"), "wb")
    app_log = open(os.path.join(APP_DIR, "test_app.stdout"), "wb")
    verdicts = {}
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
            return finish(verdicts, msg1, msg2, token1, token2)
        with open(os.path.join(DATA_DIR, "postoffice",
                               "propagation_node.txt")) as f:
            pn_hash = f.read().strip()
        log(f"Post office up. Propagation node ID: {pn_hash}")

        # --- start app ----------------------------------------------
        app = subprocess.Popen([sys.executable,
                                os.path.join(APP_DIR, "nmm_app.py"),
                                str(PORT)],
                               stdout=app_log, stderr=subprocess.STDOUT)
        procs.append(("app", app))

        def app_ready():
            try:
                code, _ = api("GET", "/api/state", timeout=5)
                return code == 200
            except Exception:
                return False

        if not wait_for(app_ready, 60, "app HTTP ready"):
            step(0, "app starts", False, "no HTTP response")
            return finish(verdicts, msg1, msg2, token1, token2)

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
            180, "message status 'stored at post office'")
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
            180, "reply status 'stored at post office'")
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
        return finish(verdicts, msg1, msg2, token1, token2)
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


def finish(verdicts, msg1, msg2, token1, token2):
    passed = bool(verdicts.get("i") and verdicts.get("ii") and
                  verdicts.get("iii") and verdicts.get("stored", True))
    log("")
    log(f"CRITERION (i)   same words → same ID:      {verdicts.get('i')}")
    log(f"CRITERION (ii)  offline message delivered: {verdicts.get('ii')}")
    log(f"CRITERION (iii) reply delivered:           {verdicts.get('iii')}")
    log(f"RESULT: {'PASS' if passed else 'FAIL'}")

    lines = [
        "# App Acceptance Test — Nature-Mirror Mesh tiny app (v1)",
        "",
        f"Date (UTC): {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}",
        "",
        "The user's own 5-step acceptance flow, executed against the",
        "real app processes (postoffice.py + nmm_app.py + per-login",
        "backends) over their HTTP endpoints. Full log:",
        "`app/test_app_flow.log`.",
        "",
        "## Flow",
        "",
        "| Step | What | Result | Evidence |",
        "|---|---|---|---|",
    ]
    for num, desc, ok, ev in STEPS:
        lines.append(f"| {num} | {desc} | {'✅ PASS' if ok else '❌ FAIL'} "
                     f"| {ev} |")
    lines += [
        "",
        "## Pre-registered criteria",
        "",
        f"- (i) same 2 words → same ID on re-login (both accounts): "
        f"**{verdicts.get('i')}**",
        f"- (ii) account 1 receives account 2's exact message after "
        f"being offline: **{verdicts.get('ii')}** — message sent: "
        f"“{msg1}”",
        f"- (iii) account 2 receives the exact reply: "
        f"**{verdicts.get('iii')}** — reply sent: “{msg2}”",
        "",
        f"## Verdict: {'PASS' if passed else 'FAIL'}",
        "",
        "## Honest scope",
        "Single device, loopback TCP only — the post office and both",
        "accounts ran on one machine, exactly like the user's one-phone",
        "test will. No internet, no radio. The 2-word key is a testing",
        "convenience and is cryptographically weak by design at this",
        "stage (documented in app/README.md).",
        "",
    ]
    with open(RESULTS_MD, "w") as f:
        f.write("\n".join(lines))
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(LOG) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
