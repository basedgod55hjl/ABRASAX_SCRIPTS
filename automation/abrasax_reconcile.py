"""ABRASAX reconcile -- OSIRISBLXCK 2026-10-31.
Kills duplicate role holders, keeping the OLDEST (most-established) one.
Order matters: kill hosts LAST so they don't respawn children we just killed.
"""
import subprocess
import sys

sys.path.insert(0, r"C:\abrasax\SCRIPTS\automation")
from abrasax_align import get_procs, ROLES

procs = get_procs()


def hits(role):
    needle = ROLES[role].lower().replace("/", "\\")
    out = []
    for p in procs:
        cl = (p.get("CommandLine") or "").replace("/", "\\").lower()
        if needle in cl:
            out.append(p)
    return sorted(out, key=lambda x: str(x.get("CreationDate")))


def kill(pid):
    r = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, text=True)
    return r.returncode == 0


# order: children before hosts
ORDER = ["reindex", "jev-server", "orchestrator", "host"]

for role in ORDER:
    hs = hits(role)
    if len(hs) <= 1:
        print(f"{role:14s} {len(hs)} instance(s) -- nothing to do")
        continue
    keep = hs[0]
    dupes = hs[1:]
    print(f"{role:14s} keep {keep['ProcessId']}, kill {[d['ProcessId'] for d in dupes]}")
    for d in dupes:
        ok = kill(d["ProcessId"])
        print(f"   kill {d['ProcessId']}: {'ok' if ok else 'FAILED'}")

print("\ndone -- run abrasax_align.py to verify")
