#!/usr/bin/env python3
"""
Nature-Mirror Mesh — mesh3 repetition harness (EVIDENCE_REVIEW remedy for
Claim 2: "3-node LXMF routed mesh forwards correctly").

Claim 2 was graded LOW in lab/results/EVIDENCE_REVIEW.md because the
post-fix evidence was n=1 (one canonical PASS after documented intermittent
failures). This harness replaces anecdote with a rate: it runs the existing
lab/lxmf_mesh3_test.py N times sequentially, unchanged, each run with a
fresh token, and records every run's exit code, token, RESULT line and —
for failures — the exact failure-mode line. The failure RATE is the datum:
the harness never stops at the first failure.

PRE-REGISTERED SUCCESS CRITERION (fixed before the first repetition run,
stated here and in lab/results/MESH3_REPETITION.md):
    >= 80% of runs PASS (exit 0, exact token match S -> T -> C)
    => 3-node transport forwarding is considered reliable.
    Below 80%, Claim 2 stays LOW and the failure modes say why.
The wrapper exits 0 iff the criterion is met, else 1.

Per-run timeout: 120 s (a run that exceeds it is killed as a process group
and recorded as FAIL / "wrapper timeout"). Between runs the harness waits
until the test's fixed TCP ports (51721/51722) refuse connections again,
so a previous run's sockets in TIME_WAIT cannot poison the next run.

Usage:
    python mesh3_repeat.py [N] [--log PATH]
    N defaults to 10. Default log: lab/results/mesh3_repeat_last.log
    (full record: summary header + every run's complete output).

Used identically for the local evidence run and in CI
(.github/workflows/mesh3.yml) — same code path both places.
"""

import argparse
import os
import re
import signal
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(BASE, "lxmf_mesh3_test.py")
RESULTS = os.path.join(BASE, "results")
DEFAULT_LOG = os.path.join(RESULTS, "mesh3_repeat_last.log")

PER_RUN_TIMEOUT = 120          # seconds, per instruction/protocol
PORTS = (51721, 51722)         # fixed ports inside lxmf_mesh3_test.py
PORT_FREE_WAIT = 30            # max seconds to wait for ports to free up
CRITERION = 0.8                # pre-registered: >= 80% PASS = reliable


def ports_free():
    for port in PORTS:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return False
        finally:
            s.close()
    return True


def wait_ports_free(max_wait=PORT_FREE_WAIT):
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if ports_free():
            return True
        time.sleep(1)
    return ports_free()


def sweep_leftovers():
    """Kill any orphaned mesh3 test processes (they would hold the ports)."""
    subprocess.run(["pkill", "-f", "lxmf_mesh3_test.py"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def failure_mode(output, exit_code, timed_out):
    """Pick the exact line that best names why a run failed."""
    if timed_out:
        return f"wrapper timeout: run exceeded {PER_RUN_TIMEOUT} s and was killed"
    lines = output.splitlines()
    for pat in (r"\[S\] TIMEOUT.*", r"\[C\] TIMEOUT.*", r"\[T\] TIMEOUT",
                r"FAIL: receiver never published.*", r"sender timed out",
                r"Address already in use", r"Traceback.*"):
        for line in lines:
            if re.search(pat, line):
                return line.strip()
    for line in lines:
        if line.startswith("RESULT: FAIL"):
            return line.strip()
    return f"no RESULT line in output (test exit code {exit_code}) — possible crash"


def run_once(index, total):
    started = time.time()
    proc = subprocess.Popen(
        [sys.executable, TEST],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        output, _ = proc.communicate(timeout=PER_RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, _ = proc.communicate()
    wall = time.time() - started
    exit_code = proc.returncode

    token_m = re.search(r"^Token:\s*(\S+)", output, re.M)
    token = token_m.group(1) if token_m else "(no token line)"
    result_m = re.search(r"^RESULT:\s*(PASS|FAIL).*$", output, re.M)
    passed = (not timed_out) and exit_code == 0 and result_m and result_m.group(1) == "PASS"
    mode = None if passed else failure_mode(output, exit_code, timed_out)
    return {
        "index": index, "token": token, "exit": exit_code,
        "passed": bool(passed), "wall": wall, "output": output,
        "result_line": result_m.group(0).strip() if result_m else "(no RESULT line)",
        "failure_mode": mode, "timed_out": timed_out,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", type=int, default=10)
    ap.add_argument("--log", default=DEFAULT_LOG)
    args = ap.parse_args()
    n = args.n

    print(f"=== mesh3 repetition: {n} sequential runs of lxmf_mesh3_test.py ===", flush=True)
    print(f"Pre-registered criterion: >= {CRITERION:.0%} PASS = forwarding reliable", flush=True)

    runs = []
    t0 = time.time()
    for i in range(1, n + 1):
        sweep_leftovers()
        if not wait_ports_free():
            print(f"[run {i}/{n}] WARNING: ports {PORTS} still busy after "
                  f"{PORT_FREE_WAIT} s — starting anyway (recorded)", flush=True)
        r = run_once(i, n)
        runs.append(r)
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[run {i}/{n}] {status} token={r['token']} exit={r['exit']} "
              f"wall={r['wall']:.1f}s" + (f" mode: {r['failure_mode']}" if r["failure_mode"] else ""),
              flush=True)
    total_wall = time.time() - t0
    npass = sum(1 for r in runs if r["passed"])
    met = (npass / n) >= CRITERION if n else False

    header = []
    header.append("=" * 72)
    header.append(f"MESH3 REPETITION RECORD — {npass}/{n} PASS")
    header.append(f"Test: lab/lxmf_mesh3_test.py (unchanged), run via lab/mesh3_repeat.py")
    header.append(f"Date (UTC): {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    header.append(f"Total wall time: {total_wall:.1f} s for {n} runs "
                  f"(per-run timeout {PER_RUN_TIMEOUT} s)")
    header.append(f"Pre-registered criterion: >= {CRITERION:.0%} PASS "
                  f"-> {'MET' if met else 'NOT MET'}")
    fails = [r for r in runs if not r["passed"]]
    if fails:
        header.append("Failure modes (exact lines):")
        for r in fails:
            header.append(f"  run {r['index']}: {r['failure_mode']}")
    else:
        header.append("Failure modes: none — all runs passed.")
    header.append("=" * 72)
    header.append("")

    body = []
    for r in runs:
        body.append("-" * 72)
        body.append(f"RUN {r['index']}/{n} — {'PASS' if r['passed'] else 'FAIL'} — "
                    f"token={r['token']} exit={r['exit']} wall={r['wall']:.1f}s")
        if r["failure_mode"]:
            body.append(f"Failure mode: {r['failure_mode']}")
        body.append(f"Result line: {r['result_line']}")
        body.append("--- full test output ---")
        body.append(r["output"].rstrip())
        body.append("")
    body.append(f"MESH3 REPETITION: {npass}/{n} PASS "
                f"(criterion >= {CRITERION:.0%}: {'MET' if met else 'NOT MET'})")

    os.makedirs(RESULTS, exist_ok=True)
    with open(args.log, "w") as f:
        f.write("\n".join(header + body) + "\n")
    print(f"\nMESH3 REPETITION: {npass}/{n} PASS "
          f"(criterion >= {CRITERION:.0%}: {'MET' if met else 'NOT MET'})", flush=True)
    print(f"Full record written to {args.log}", flush=True)
    return 0 if met else 1


if __name__ == "__main__":
    sys.exit(main())
