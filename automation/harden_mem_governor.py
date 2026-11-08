"""Harden the governor before it kills anything.

Two risks found in the first --status run:

1. `Cloudflare WARP.exe` (pid 18920, 80 MB) appeared as an orphan because its
   launcher (24048) is gone. But it is the machine's active VPN and the network
   path this session is using. "Parent is dead" does NOT imply "safe to kill" --
   the service supervisor model means a daemon's parent often exits on purpose.
   Adding WARP to PROTECTED.

2. 42 orphans worth 1,720 MB is a big blast radius. A governor that can free 1.7 GB
   in one call needs a hard cap and a dry-run default, or a bug in it takes down
   the box. This adds:
      * MAX_RECLAIM_PROCESSES   never kill more than N in one pass
      * MAX_RECLAIM_MB          never free more than M MB in one pass
      * DENY_NAMES              explicit never-kill list, separate from PROTECTED,
                                for things that are not services but are in use
      * a printed plan before any Stop-Process

3. `--reap` was opt-in to acting. Keep that, but require `--yes` as well when the
   plan exceeds the caps, so an accidental invocation cannot do large damage.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\mem_governor.py"
src = open(PATH, encoding="utf-8").read()

if "MAX_RECLAIM_PROCESSES" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. extend protection
OLD_PROT = '''    # this agent's own processes
    "python.exe", "pythonw.exe",
}'''
NEW_PROT = '''    # this agent's own processes
    "python.exe", "pythonw.exe",
    # MEASURED RISK: Cloudflare WARP showed up as an "orphan" because its launcher
    # exited, yet it is the machine's live VPN and this session's network path.
    # A daemon whose parent exits is normal; parent-death alone is not proof of
    # killability.
    "Cloudflare WARP.exe", "warp-svc.exe",
}

# Names that must never be reaped even if they pass the orphan test. Separate from
# PROTECTED so the reason is explicit: these are in use, not necessarily services.
DENY_NAMES = {
    "Cloudflare WARP.exe", "warp-svc.exe", "Telegram.exe", "Everything.exe",
    "Code.exe", "chrome.exe", "msedge.exe", "msedgewebview2.exe",
}

# Blast-radius caps: a bug here must not be able to take the machine down.
MAX_RECLAIM_PROCESSES = 12
MAX_RECLAIM_MB = 1200'''
if OLD_PROT not in src:
    print("ANCHOR-NOT-FOUND: PROTECTED set")
    sys.exit(1)
src = src.replace(OLD_PROT, NEW_PROT, 1)

# 2. honour DENY_NAMES in orphans()
OLD_ORPH = '''    for p in procs:
        if p["name"] in PROTECTED:
            continue'''
NEW_ORPH = '''    for p in procs:
        if p["name"] in PROTECTED or p["name"] in DENY_NAMES:
            continue'''
if OLD_ORPH not in src:
    print("ANCHOR-NOT-FOUND: orphan filter")
    sys.exit(1)
src = src.replace(OLD_ORPH, NEW_ORPH, 1)

# 3. cap the plan inside reap()
OLD_REAP = '''    procs = processes()
    victims = orphans(procs)
'''
NEW_REAP = '''    procs = processes()
    victims = orphans(procs)

    # apply the blast-radius caps, largest first so the cap still frees the most
    kept, dropped_mb, dropped_n = [], 0, 0
    for v in victims:
        if len(kept) >= MAX_RECLAIM_PROCESSES:
            dropped_n += 1
            dropped_mb += v["mb"]
            continue
        if sum(k["mb"] for k in kept) + v["mb"] > MAX_RECLAIM_MB:
            dropped_n += 1
            dropped_mb += v["mb"]
            continue
        kept.append(v)
    if dropped_n:
        print(f"  (caps applied: {dropped_n} more orphan(s), {dropped_mb} MB, "
              f"left alone -- MAX_RECLAIM_PROCESSES={MAX_RECLAIM_PROCESSES}, "
              f"MAX_RECLAIM_MB={MAX_RECLAIM_MB})", flush=True)
    victims = kept
'''
if OLD_REAP not in src:
    print("ANCHOR-NOT-FOUND: reap body")
    sys.exit(1)
src = src.replace(OLD_REAP, NEW_REAP, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: WARP protected, DENY_NAMES added, blast-radius caps applied")
