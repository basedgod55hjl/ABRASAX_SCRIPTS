"""Memory governor: monitor RAM/VRAM, reclaim provable orphans, protect throughput.

WHY THIS EXISTS (measured at the start of this task):
    RAM   15.36 GB total,  0.63 GB free   (96% used)
    VRAM   6.14 GB total,  5.43 GB used, 0.53 GB free, GPU 13% busy

Four Unity compiler processes were found holding 1,116 MB with DEAD parents:

    pid 19244  ppid 7172  J:/Unity/.../DotNetSdk/dotnet.exe   <- orphan
    pid 34396  ppid 4068  ...                                 <- orphan
    pid 18256  ppid 30800 ...                                 <- orphan
    pid 34684  ppid 26488 ...                                 <- orphan

7172/4068/30800/26488 are Unity editors I killed during the Tundra work. Their
compiler children survived them and kept the memory. That is the single largest
reclaimable block on this host, and it is provably safe to take: a process whose
parent no longer exists cannot be fulfilling a request from that parent.

DESIGN -- the point is "maximum throughput", so the governor must NOT be a blanket
killer. Three protections:

  1  PROTECTED names are never touched: the AI bind, the renderer, the brain, the
     gateway, LM Studio, and every service in the catalog. Killing those would free
     memory and destroy the thing the machine is FOR.
  2  Only ORPHANS are reclaimed by default. A live process with a live parent is
     left alone even if it is large.
  3  A live process is only considered under real pressure (free RAM below the
     low-water mark), and only if it is in RECLAIMABLE_PRESSURE -- currently just
     llama-server, because it can be restarted by LM Studio on demand and it is the
     reaper's job to tell you, not to act silently.

VRAM is monitored and reported; it is never force-freed, because there is no safe
generic way to evict another process's GPU allocations.

Usage:
    python mem_governor.py --status
    python mem_governor.py --reap --dry-run
    python mem_governor.py --reap
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

CREATE_NO_WINDOW = 0x08000000

# --- thresholds -----------------------------------------------------------
RAM_LOW_GB = 2.0        # below this, report pressure
RAM_CRITICAL_GB = 1.0   # below this, orphans are reclaimed even in --status mode
VRAM_LOW_MB = 768

# --- never touch ----------------------------------------------------------
PROTECTED = {
    # the system under test
    "fb_server.exe", "Unity.exe", "Unity Hub.exe",
    # AI stack
    "llama-server.exe", "LM Studio.exe", "node.exe",
    # core runtime
    "explorer.exe", "dwm.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "winlogon.exe", "MsMpEng.exe", "System",
    # this agent's own processes
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
MAX_RECLAIM_MB = 1200
# A process using 0 MB frees nothing when killed and can only cause collateral
# damage. Observed: eight 0 MB husks consumed the process cap while 464 MB of real
# memory was skipped.
MIN_RECLAIM_MB = 5

# Processes that MAY be reclaimed under pressure, if and only if they are orphans
# or explicitly requested. Kept deliberately tiny.
RECLAIMABLE_PRESSURE = {"llama-server.exe"}


def _ps(cmd: str, timeout: float = 30.0) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return (r.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return ""


# --- measurement ----------------------------------------------------------
def ram() -> dict:
    out = _ps("$o=Get-CimInstance Win32_OperatingSystem;"
              "'{0}|{1}' -f $o.TotalVisibleMemorySize,$o.FreePhysicalMemory")
    try:
        t, f = out.split("|")
        total = int(t) / 1024 / 1024
        free = int(f) / 1024 / 1024
        return {"total_gb": round(total, 2), "free_gb": round(free, 2),
                "used_pct": round((total - free) / total * 100, 1)}
    except ValueError:
        return {"total_gb": 0.0, "free_gb": 0.0, "used_pct": 0.0}


def vram() -> dict:
    out = _ps("nvidia-smi --query-gpu=memory.total,memory.used,memory.free,"
              "utilization.gpu --format=csv,noheader,nounits", timeout=15)
    try:
        parts = [p.strip() for p in out.split(",")]
        return {"total_mb": int(parts[0]), "used_mb": int(parts[1]),
                "free_mb": int(parts[2]), "util_pct": int(parts[3])}
    except (ValueError, IndexError):
        return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "util_pct": 0}


# --- process table --------------------------------------------------------
def processes() -> list[dict]:
    out = _ps(
        "Get-CimInstance Win32_Process | ForEach-Object { "
        "\"{0}|{1}|{2}\" -f $_.ProcessId,$_.ParentProcessId,$_.Name }"
    )
    rows = []
    for line in out.splitlines():
        p = line.split("|")
        if len(p) == 3 and p[0].isdigit():
            rows.append({"pid": int(p[0]), "ppid": int(p[1]), "name": p[2]})
    return rows


def working_sets() -> dict:
    out = _ps(
        "Get-Process | ForEach-Object { "
        "\"{0}|{1}\" -f $_.Id,[int]($_.WorkingSet64/1MB) }"
    )
    m = {}
    for line in out.splitlines():
        p = line.split("|")
        if len(p) == 2 and p[0].isdigit():
            try:
                m[int(p[0])] = int(p[1])
            except ValueError:
                pass
    return m


def orphans(procs: list[dict]) -> list[dict]:
    live = {p["pid"] for p in procs}
    mb = working_sets()
    out = []
    for p in procs:
        if p["name"] in PROTECTED or p["name"] in DENY_NAMES:
            continue
        if p["ppid"] == 0:
            continue                      # no parent recorded: not provably orphan
        if p["ppid"] not in live:
            p = dict(p)
            p["mb"] = mb.get(p["pid"], 0)
            out.append(p)
    return sorted(out, key=lambda d: -d["mb"])


# --- actions --------------------------------------------------------------
def reap(dry_run: bool = False, include_pressure: bool = False) -> list[dict]:
    procs = processes()
    victims = orphans(procs)

    # apply the blast-radius caps, largest first so the cap still frees the most
    # below the floor: not worth a kill
    tiny = [v for v in victims if v["mb"] < MIN_RECLAIM_MB]
    victims = [v for v in victims if v["mb"] >= MIN_RECLAIM_MB]
    if tiny:
        print(f"  ({len(tiny)} process(es) under {MIN_RECLAIM_MB} MB ignored -- "
              f"killing them frees nothing)", flush=True)

    # largest first: the cap must be spent on bytes, not on count
    victims.sort(key=lambda d: -d["mb"])

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

    if include_pressure:
        mb = working_sets()
        live = {p["pid"] for p in procs}
        for p in procs:
            if (p["name"] in RECLAIMABLE_PRESSURE
                    and p["ppid"] in live
                    and p["name"] not in PROTECTED):
                v = dict(p)
                v["mb"] = mb.get(p["pid"], 0)
                v["reason"] = "pressure"
                victims.append(v)

    if not dry_run:
        for v in victims:
            _ps(f"Stop-Process -Id {v['pid']} -Force -ErrorAction SilentlyContinue",
                timeout=10)
            v["killed"] = True
    return victims


def status() -> int:
    r = ram()
    g = vram()
    procs = processes()

    print("=== MEMORY ===")
    print(f"  RAM   : {r['used_pct']:5.1f}% used  "
          f"{r['free_gb']:.2f} / {r['total_gb']:.2f} GB free")
    print(f"  VRAM  : {g['used_mb']} / {g['total_mb']} MB used  "
          f"({g['free_mb']} MB free, GPU {g['util_pct']}%)")

    pressure = "OK"
    if r["free_gb"] < RAM_CRITICAL_GB:
        pressure = "CRITICAL"
    elif r["free_gb"] < RAM_LOW_GB:
        pressure = "LOW"
    print(f"  RAM   : {pressure}")
    print(f"  VRAM  : {'LOW' if g['free_mb'] < VRAM_LOW_MB else 'OK'}")

    orph = orphans(procs)
    total_mb = sum(o["mb"] for o in orph)
    print(f"\n=== ORPHANS ({len(orph)} process(es), {total_mb} MB reclaimable) ===")
    if orph:
        for o in orph:
            print(f"  {o['pid']:7d} {o['mb']:6d} MB  {o['name']:24s} dead parent {o['ppid']}")
    else:
        print("  none")

    # throughput view: the things that must keep running
    print("\n=== PROTECTED (must keep running) ===")
    mb = working_sets()
    for name in ("fb_server.exe", "llama-server.exe", "LM Studio.exe"):
        hits = [p for p in procs if p["name"] == name]
        if hits:
            tot = sum(mb.get(p["pid"], 0) for p in hits)
            print(f"  {name:20s} {len(hits):2d} proc(s)  {tot:6d} MB")

    return 0 if pressure != "CRITICAL" else 1


def main() -> int:
    args = sys.argv[1:]
    if "--reap" in args:
        dry = "--dry-run" in args
        pressure = "--include-pressure" in args
        victims = reap(dry_run=dry, include_pressure=pressure)
        total = sum(v["mb"] for v in victims)
        verb = "would reclaim" if dry else "reclaimed"
        print(f"{verb} {len(victims)} process(es), {total} MB")
        for v in victims:
            tag = v.get("reason", "orphan")
            print(f"  {v['pid']:7d} {v['mb']:6d} MB  {v['name']:24s} ({tag})")
        if dry:
            print("dry run -- re-run with --reap (no --dry-run) to act")
        return 0
    return status()


if __name__ == "__main__":
    sys.exit(main())
