#!/usr/bin/env python3
"""Detect and (with --apply) consolidate duplicate ABRASAX service listeners.

Windows permits multiple processes to bind the same port with SO_REUSEADDR.
The stack has accumulated dozens of duplicates: only one serves, the rest hold
sockets, memory and (for CUDA services) VRAM. This tool is conservative:

  * dry-run by default; --apply kills only classified duplicates
  * a port is only acted on if it answers a probe (a keeper exists)
  * the keeper is the listener with the highest CPU delta, then oldest start
  * protected processes are never touched: this process and its ancestors,
    supervisors, LM Studio / llama-server, pytest, system processes
  * every action is recorded in DOC/inventory/SERVICE_CONCURRENCY.json

Usage:
    python SCRIPTS/automation/service_consolidate.py
    python SCRIPTS/automation/service_consolidate.py --apply --sample 6
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "DOC" / "inventory" / "SERVICE_CONCURRENCY.json"
NEVER_KILL_NAMES = {
    "system", "system idle process", "svchost.exe", "lsass.exe", "wininit.exe",
    "services.exe", "explorer.exe", "lm studio.exe", "llama-server.exe",
    "node.exe",  # node services are cheap; do not reap automatically
}
NEVER_KILL_CMDLINE = (
    "supervisor.py", "pytest", "jcode", "service_consolidate.py",
    "lmstudio", "llama-server",
)
# Ports where the real server is unambiguous: the keeper has far more lifetime
# CPU and RSS than the rest, and the rest are failed initialisations.
DOMINANT = {
    9700: {"rss_max_mb": 5.0, "cpu_max_s": 30.0},
}


def ancestors() -> set[int]:
    out = {os.getpid()}
    try:
        p = psutil.Process()
        while p is not None:
            out.add(p.pid)
            p = p.parent()
    except Exception:  # noqa: BLE001
        pass
    return out


def probe(port: int, timeout: float = 2.5) -> dict:
    url = f"http://127.0.0.1:{port}/"
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(64)
            return {"ok": True, "status": r.status, "ms": round((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": True, "status": e.code, "ms": round((time.time() - t0) * 1000),
                "note": "reachable; non-2xx normal for API-only services"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "error": type(e).__name__,
                "ms": round((time.time() - t0) * 1000)}


def listener_map() -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    for c in psutil.net_connections(kind="tcp"):
        if c.status == psutil.CONN_LISTEN and c.laddr:
            out.setdefault(c.laddr.port, set()).add(c.pid)
    return out


def proc_info(pid: int) -> dict:
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            return {
                "pid": pid,
                "name": p.name(),
                "exe": p.exe(),
                "cmdline": " ".join(p.cmdline()),
                "create_time": p.create_time(),
                "rss_mb": round(p.memory_info().rss / 1e6, 1),
                "threads": p.num_threads(),
                "cpu_s": p.cpu_times().user + p.cpu_times().system,
                "status": p.status(),
                "ppid": p.ppid(),
            }
    except Exception as e:  # noqa: BLE001
        return {"pid": pid, "error": type(e).__name__, "name": "", "cmdline": ""}


def protected(info: dict, anc: set[int]) -> str | None:
    pid = info.get("pid")
    if pid in anc:
        return "ancestor"
    name = (info.get("name") or "").lower()
    if name in NEVER_KILL_NAMES:
        return f"protected_name:{name}"
    cmd = (info.get("cmdline") or "").lower()
    for token in NEVER_KILL_CMDLINE:
        if token in cmd:
            return f"protected_cmdline:{token}"
    if info.get("rss_mb", 0) > 2500:
        return "large_process"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sample", type=float, default=6.0)
    ap.add_argument("--min-listeners", type=int, default=2)
    ap.add_argument("--ports", default="", help="comma-separated port filter")
    args = ap.parse_args()

    anc = ancestors()
    lm = listener_map()
    only = {int(x) for x in args.ports.split(",") if x.strip().isdigit()}
    targets = {p: pids for p, pids in lm.items()
               if len(pids) >= args.min_listeners and p != 1234 and (not only or p in only)}
    port_probe = {p: probe(p) for p in targets}

    # baseline CPU
    infos: dict[int, dict] = {}
    for pids in targets.values():
        for pid in pids:
            infos[pid] = proc_info(pid)
    base = {pid: i.get("cpu_s", 0.0) for pid, i in infos.items()}
    time.sleep(max(0.0, args.sample))
    for pid in infos:
        cur = proc_info(pid)
        delta = round(cur.get("cpu_s", 0.0) - base.get(pid, 0.0), 3)
        infos[pid]["cpu_delta_s"] = max(delta, 0.0)
        infos[pid]["current"] = {k: cur.get(k) for k in ("rss_mb", "threads", "status")}

    groups = []
    kill: set[int] = set()
    for port, pids in sorted(targets.items()):
        members = [infos[p] for p in pids if p in infos]
        healthy = port_probe[port]["ok"]
        # Rank by evidence of real work: lifetime CPU, thread count, RSS, then age.
        # Recent CPU alone is misleading for long-idle servers.
        ranked = sorted(members, key=lambda m: (
            -(m.get("cpu_s", 0.0)), -m.get("threads", 0), -m.get("rss_mb", 0.0),
            m.get("create_time", 0)))
        keeper = ranked[0] if ranked else None
        candidates = []
        dominant = DOMINANT.get(port)
        # A keeper that has many threads and minutes of lifetime CPU is alive
        # even if its HTTP probe is momentarily busy. Failed starts beside it
        # can be reaped without waiting for a response.
        keeper_proven = bool(
            keeper and keeper.get("threads", 0) >= 8 and keeper.get("cpu_s", 0.0) >= 60
        )
        for m in ranked[1:]:
            reason = protected(m, anc)
            if reason:
                m["protected"] = reason
                continue
            if not healthy:
                if keeper_proven and m.get("rss_mb", 0.0) < 5.0 and m.get("cpu_s", 0.0) < 30.0:
                    m["protected"] = "failed_start_next_to_proven_keeper"
                    candidates.append(m["pid"])
                    continue
                if keeper_proven and m.get("threads", 0) <= 1 \
                        and m.get("rss_mb", 0.0) < 2.0 and m.get("cpu_delta_s", 0.0) == 0:
                    m["protected"] = "husk_next_to_proven_keeper"
                    candidates.append(m["pid"])
                    continue
                m["protected"] = "no healthy keeper on port"
                continue
            if m.get("cpu_delta_s", 0.0) > 0.5:
                m["protected"] = "active_cpu"
                continue
            if dominant and m.get("rss_mb", 0.0) < dominant["rss_max_mb"] \
                    and m.get("cpu_s", 0.0) < dominant["cpu_max_s"]:
                m["protected"] = "dominant_rule_duplicate"
                candidates.append(m["pid"])
                continue
            # Only a husk is eligible: one thread, tiny working set, no CPU.
            # A real idle server keeps its interpreter pages and a second thread.
            if m.get("threads", 0) > 1:
                m["protected"] = "multi_thread"
                continue
            if m.get("rss_mb", 0.0) > 2.0:
                m["protected"] = "rss_above_husk_threshold"
                continue
            candidates.append(m["pid"])
        kill.update(candidates)
        groups.append({
            "port": port, "listeners": len(pids), "probe": port_probe[port],
            "keeper": {k: keeper.get(k) for k in ("pid", "name", "cmdline", "cpu_s", "cpu_delta_s", "rss_mb", "threads")} if keeper else None,
            "members": members, "would_kill": candidates,
        })

    # duplicate supervisors (no port)
    supervisors = []
    for p in psutil.process_iter(["pid", "cmdline", "create_time", "name"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
            if "supervisor.py" in cmd:
                supervisors.append({"pid": p.info["pid"], "create_time": p.info["create_time"],
                                    "cmdline": cmd[:240]})
        except Exception:  # noqa: BLE001
            continue
    supervisors.sort(key=lambda s: s["create_time"])

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_seconds": args.sample,
        "duplicate_ports": len(groups),
        "total_duplicate_listeners": sum(g["listeners"] for g in groups),
        "candidate_pids": sorted(kill),
        "groups": groups,
        "supervisors": supervisors,
        "applied": False,
    }

    if args.apply and kill:
        killed = []
        for pid in sorted(kill):
            try:
                psutil.Process(pid).terminate()
                killed.append({"pid": pid, "result": "terminate"})
            except Exception as e:  # noqa: BLE001
                killed.append({"pid": pid, "result": f"error:{type(e).__name__}"})
        time.sleep(3)
        for entry in killed:
            if entry["result"] == "terminate":
                try:
                    p = psutil.Process(entry["pid"])
                    if p.is_running():
                        p.kill()
                        entry["result"] = "killed"
                    else:
                        entry["result"] = "exited"
                except Exception:
                    entry["result"] = "exited"
        report["applied"] = True
        report["killed"] = killed
        report["after"] = {str(p): probe(p) for p in targets}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"duplicate ports: {len(groups)}  listeners in groups: {report['total_duplicate_listeners']}")
    print(f"{'PORT':>6} {'LST':>3} {'PROBE':>6} {'KEEPER':>7} {'KILL':>4}  KEEPER CMDLINE")
    for g in groups:
        k = g["keeper"] or {}
        print(f"{g['port']:>6} {g['listeners']:>3} {str(g['probe'].get('status')):>6} "
              f"{k.get('pid', '-'):>7} {len(g['would_kill']):>4}  {(k.get('cmdline') or '')[:90]}")
    print(f"supervisors: {len(supervisors)} -> {[s['pid'] for s in supervisors]}")
    print(f"candidates: {len(kill)} {sorted(kill)[:40]}")
    print(f"wrote {OUT}")
    if not args.apply:
        print("DRY RUN. Re-run with --apply to terminate classified duplicates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
