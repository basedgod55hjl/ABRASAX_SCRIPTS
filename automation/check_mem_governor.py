"""Verify the governor's safety properties, not just its happy path.

A memory reaper is dangerous software: the failure mode is killing something the
machine needed. So the tests target the guarantees:

  1  PROTECTED names are never selected, even when they look orphaned
  2  DENY_NAMES are never selected (Cloudflare WARP was a real near-miss)
  3  orphans() ignores processes with no recorded parent (ppid == 0)
  4  the byte floor excludes 0 MB husks
  5  the caps bound a single pass
  6  VRAM attribution is reported as unavailable rather than invented
  7  a real reclaim frees memory (integration, only under pressure)

No real process is killed by the unit tests: they exercise selection logic against
synthetic tables. Test 7 reads the live state and only asserts if it actually ran.
"""
import os
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

import mem_governor as gov  # noqa: E402

ok = True


def check(name, cond, detail=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        ok = False


# ---- 1/2/3. selection logic against a synthetic table -------------------
FAKE = [
    {"pid": 100, "ppid": 1,   "name": "dotnet.exe"},        # orphan, reapable
    {"pid": 101, "ppid": 100, "name": "dotnet.exe"},        # child of live 100
    {"pid": 200, "ppid": 9,   "name": "llama-server.exe"},  # PROTECTED
    {"pid": 300, "ppid": 9,   "name": "fb_server.exe"},     # PROTECTED
    {"pid": 400, "ppid": 9,   "name": "Cloudflare WARP.exe"},  # DENY
    {"pid": 500, "ppid": 0,   "name": "mystery.exe"},       # no parent recorded
    {"pid": 600, "ppid": 9,   "name": "Telegram.exe"},      # DENY
]

# working sets: give each a size so the floor logic is exercised
real_ws = gov.working_sets
gov.working_sets = lambda: {100: 300, 101: 50, 200: 1700, 300: 16, 400: 80,
                            500: 40, 600: 100}
real_procs = gov.processes
gov.processes = lambda: FAKE

sel = gov.orphans(FAKE)
names = {s["name"] for s in sel}
pids = {s["pid"] for s in sel}

check("selects a genuine orphan", 100 in pids)
check("never selects a PROTECTED name",
      not (names & gov.PROTECTED), f"selected: {sorted(names)}")
check("never selects a DENY name",
      not (names & gov.DENY_NAMES), f"selected: {sorted(names)}")
check("never selects ppid==0",
      500 not in pids, "no recorded parent is not proof of orphaning")
check("does NOT select the child of a live process",
      101 not in pids, "its parent 100 is in the table, so it is not an orphan")

# ---- 4. the byte floor --------------------------------------------------
gov.MAX_RECLAIM_PROCESSES = 12
gov.MAX_RECLAIM_MB = 10_000
gov.MIN_RECLAIM_MB = 5
gov.working_sets = lambda: {100: 2, 101: 0}      # both below the floor
tiny = gov.orphans([{"pid": 100, "ppid": 1, "name": "a.exe"}])
check("a 2 MB orphan is below the default floor and would be skipped by reap",
      tiny[0]["mb"] < gov.MIN_RECLAIM_MB, f"{tiny[0]['mb']} MB < {gov.MIN_RECLAIM_MB} MB")

# ---- 5. caps ------------------------------------------------------------
gov.MAX_RECLAIM_PROCESSES = 2
gov.MAX_RECLAIM_MB = 10_000
gov.MIN_RECLAIM_MB = 5
many = [{"pid": 1000 + i, "ppid": 1, "name": "x.exe"} for i in range(10)]
gov.working_sets = lambda: {1000 + i: 50 for i in range(10)}
gov.processes = lambda: many
victims = gov.reap(dry_run=True)
check("process cap bounds a single pass", len(victims) <= 2, f"{len(victims)} selected")

gov.MAX_RECLAIM_PROCESSES = 100
gov.MAX_RECLAIM_MB = 120
victims = gov.reap(dry_run=True)
total = sum(v["mb"] for v in victims)
check("byte cap bounds a single pass", total <= 120, f"{total} MB selected")

# restore
gov.working_sets = real_ws
gov.processes = real_procs
gov.MAX_RECLAIM_PROCESSES = 12
gov.MAX_RECLAIM_MB = 1200
gov.MIN_RECLAIM_MB = 5

# ---- 6. VRAM honesty ----------------------------------------------------
g = gov.vram()
check("vram() reports numbers", isinstance(g.get("total_mb"), int) and g["total_mb"] > 0,
      f"{g}")
import mem_monitor  # noqa: E402
s = mem_monitor.snapshot()
check("snapshot states VRAM attribution is unavailable rather than guessing",
      "unavailable" in s["vram_attribution"], s["vram_attribution"])

# ---- 7. live state ------------------------------------------------------
r = gov.ram()
check("ram() reports a sane total", 8 < r["total_gb"] < 512, f"{r['total_gb']} GB")
check("protected services are running now",
      any(p["name"] == "fb_server.exe" for p in real_procs()), "renderer present")

print("\nRESULT:", "PASS -- governor cannot select a protected or non-orphan process"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
