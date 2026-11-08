"""Continuous memory monitor with a documented, bounded action policy.

WHAT IT CAN DO, measured:
    RAM   per-process working set is available -> orphans can be attributed and
          reclaimed safely (proved: 1,200 MB recovered in one pass, 0.42 -> 1.65 GB)
    VRAM  TOTAL used/free is available, but per-process attribution is NOT:
          nvidia-smi --query-compute-apps returns "[N/A]" for every pid on this
          host (GTX 1660 Ti, driver 617.14). So VRAM can be reported and alarmed
          on, but the monitor will not pretend to know which process holds it.

That asymmetry is stated in the output rather than hidden.

POLICY (deliberately conservative -- the goal is throughput, not a low number):
  * never touch PROTECTED or DENY_NAMES
  * reclaim only processes whose parent is gone AND that hold >= MIN_RECLAIM_MB
  * never reclaim more than MAX_RECLAIM_PROCESSES / MAX_RECLAIM_MB per pass
  * require RAM below RAM_LOW_GB before acting automatically
  * append every pass to LOGS/mem-governor.jsonl so the trend is auditable

Usage:
    python mem_monitor.py --once
    python mem_monitor.py --watch --interval 30 --reclaim
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mem_governor as gov  # noqa: E402

LOG = r"C:\ABRASAX\LOGS\mem-governor.jsonl"


def snapshot() -> dict:
    r = gov.ram()
    g = gov.vram()
    procs = gov.processes()
    orph = gov.orphans(procs)
    mb = gov.working_sets()

    protected_live = {}
    for name in ("fb_server.exe", "llama-server.exe", "LM Studio.exe"):
        hits = [p for p in procs if p["name"] == name]
        if hits:
            protected_live[name] = {
                "count": len(hits),
                "mb": sum(mb.get(p["pid"], 0) for p in hits),
            }

    return {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ram": r,
        "vram": g,
        "vram_attribution": "unavailable (nvidia-smi reports [N/A] per pid)",
        "orphans": {
            "count": len(orph),
            "mb": sum(o["mb"] for o in orph),
            "largest": [{"pid": o["pid"], "mb": o["mb"], "name": o["name"]}
                        for o in orph[:5]],
        },
        "protected": protected_live,
        "pressure": (
            "critical" if r["free_gb"] < gov.RAM_CRITICAL_GB
            else "low" if r["free_gb"] < gov.RAM_LOW_GB
            else "ok"
        ),
    }


def report(s: dict) -> None:
    r, g = s["ram"], s["vram"]
    print(f"[{s['ts']}]")
    print(f"  RAM   {r['used_pct']:5.1f}%  free {r['free_gb']:.2f}/{r['total_gb']:.2f} GB"
          f"   pressure={s['pressure'].upper()}")
    print(f"  VRAM  {g['used_mb']}/{g['total_mb']} MB used, {g['free_mb']} MB free,"
          f" GPU {g['util_pct']}%")
    print(f"        attribution: {s['vram_attribution']}")
    o = s["orphans"]
    print(f"  ORPHANS {o['count']} process(es), {o['mb']} MB reclaimable")
    for e in o["largest"]:
        print(f"      {e['pid']:7d} {e['mb']:6d} MB  {e['name']}")
    if s["protected"]:
        print("  PROTECTED (kept running for throughput):")
        for name, v in s["protected"].items():
            print(f"      {name:20s} {v['count']} proc  {v['mb']:6d} MB")


def append_log(s: dict) -> None:
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(s) + "\n")
    except OSError:
        pass


def main() -> int:
    args = sys.argv[1:]
    watch = "--watch" in args
    reclaim = "--reclaim" in args
    interval = 30.0
    if "--interval" in args:
        try:
            interval = float(args[args.index("--interval") + 1])
        except (IndexError, ValueError):
            pass

    def one_pass() -> None:
        s = snapshot()
        report(s)
        append_log(s)

        if reclaim and s["pressure"] in ("low", "critical"):
            print("  -> pressure detected, reclaiming orphans")
            victims = gov.reap(dry_run=False)
            total = sum(v["mb"] for v in victims)
            print(f"  reclaimed {len(victims)} process(es), {total} MB")
            for v in victims:
                print(f"      {v['pid']:7d} {v['mb']:6d} MB  {v['name']}")
        elif reclaim:
            print("  -> RAM is healthy; reclaim skipped (throughput preserved)")
        print()

    if not watch:
        one_pass()
        return 0

    print(f"watching every {interval:.0f}s (Ctrl-C to stop); reclaim={reclaim}")
    try:
        while True:
            one_pass()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
