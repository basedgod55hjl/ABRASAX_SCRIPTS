#!/usr/bin/env python3
"""ABRASAX ALIGN WATCHDOG -- OSIRISBLXCK 2026-10-31.

Continuously enforces the "one owner per role" invariant. Loops every N sec:
  1. audit roles (no duplicates, no stale locks)
  2. if duplicates appear -> reconcile (kill newest, keep oldest, hosts last)
  3. append every action to LOGS/align_watchdog.jsonl
  4. never kills the singleton `host` unless a duplicate of it exists

Run:  python SCRIPTS\\automation\\abrasax_watchdog_align.py --interval 45
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from abrasax_align import get_procs, ROLES  # noqa: E402

ROOT = os.environ.get("ABRASAX_ROOT", r"C:\abrasax")
AUDIT_LOG = os.path.join(ROOT, "LOGS", "align_watchdog.jsonl")

ORDER = ["reindex", "jev-server", "jev-fused", "buildloop", "brain-serve",
         "overlay", "ui-http", "orchestrator", "host"]


def log(event):
    event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def hits(procs, role):
    needle = ROLES[role].lower().replace("/", "\\")
    out = []
    for p in procs:
        cl = (p.get("CommandLine") or "").replace("/", "\\").lower()
        if needle and needle in cl:
            out.append(p)
    return sorted(out, key=lambda x: str(x.get("CreationDate")))


def kill(pid):
    return subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                          capture_output=True).returncode == 0


def sweep():
    procs = get_procs()
    actions = []
    for role in ORDER:
        hs = hits(procs, role)
        if len(hs) > 1:
            keep, dupes = hs[0], hs[1:]
            for d in dupes:
                ok = kill(d["ProcessId"])
                actions.append({"role": role, "action": "kill",
                                "pid": d["ProcessId"], "ok": ok,
                                "kept": keep["ProcessId"]})
    return actions


def main():
    interval = 45
    if "--interval" in sys.argv:
        interval = int(sys.argv[sys.argv.index("--interval") + 1])
    log({"event": "watchdog_start", "interval": interval, "pid": os.getpid()})
    while True:
        try:
            acts = sweep()
            if acts:
                log({"event": "reconciled", "actions": acts})
                print("reconciled:", acts, flush=True)
            else:
                log({"event": "ok"})
        except Exception as e:
            log({"event": "error", "error": repr(e)})
        time.sleep(interval)


if __name__ == "__main__":
    main()
