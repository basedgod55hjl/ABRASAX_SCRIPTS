#!/usr/bin/env python3
"""Supervise one ABRASAX port: reduce duplicate listeners to one and, if the
port is left unserved, start the canonical service.

Dry-run by default. --apply:
  1. lists listeners on the port
  2. keeps the process with the most lifetime CPU (evidence of real work)
  3. terminates only processes whose command line matches the service signature
  4. re-probes; if unserved, starts the canonical command from the correct cwd
  5. records every action in DOC/inventory/PORT_SUPERVISION.json

Usage:
    python SCRIPTS/automation/service_supervise_port.py --port 9625
    python SCRIPTS/automation/service_supervise_port.py --port 9625 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
SUB = ROOT / "TOOLS" / "source-tools" / "subsystems"
OUT = ROOT / "DOC" / "inventory" / "PORT_SUPERVISION.json"

# The stack's CUDA torch lives in the project venv. The global Python imports
# torch but reports cuda_available=False, which silently downgrades the brain
# services to numpy (measured: backend='numpy' after a restart).
_VENV_PY = ROOT / "PYTHON" / ".venv_gui" / "Scripts" / "python.exe"
PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable

SPECS: dict[int, dict] = {
    8765: {
        "name": "filetool", "signature": "filetool.py",
        "cwd": ROOT / "TOOLS" / "source-tools" / "subsystems" / "filetool",
        "cmd": [PYTHON, "filetool.py"],
    },
    9001: {
        "name": "abrasax-gateway", "signature": "abrasax gateway",
        "cwd": ROOT,
        "cmd": [PYTHON, "-m", "abrasax", "gateway", "--port", "9001"],
    },
    9624: {
        "name": "cellbrain", "signature": "abraxas_cellbrain.py",
        "cwd": ROOT / "TOOLS" / "source-tools" / "brains",
        "cmd": [PYTHON, "abraxas_cellbrain.py", "--serve", "--port", "9624",
                "--autoloop", "5", "--reciprocal"],
    },
    9625: {
        "name": "synaptic-brain", "signature": "abraxas_synaptic_server.py",
        "cwd": ROOT / "TOOLS" / "source-tools" / "brains",
        "cmd": [PYTHON, "abraxas_synaptic_server.py", "--serve", "--port", "9625",
                "--autoloop", "5", "--resume"],
    },
    9626: {
        "name": "abrasax-brain", "signature": "abrasax.brain",
        "cwd": ROOT,
        "cmd": [PYTHON, "-m", "abrasax.brain", "serve", "--port", "9626"],
    },
    9627: {
        "name": "floating-brain-overlay", "signature": "imgui_overlay.py",
        "cwd": ROOT,
        "cmd": [PYTHON, "ENGINE/floating_brain/imgui_overlay.py",
                "--width", "760", "--height", "760", "--topmost", "--borderless"],
    },
    9700: {
        "name": "floating-brain", "signature": "fb_server.exe",
        "cwd": ROOT / "ENGINE" / "floating_brain" / "cuda" / "bin",
        "cmd": [str(ROOT / "ENGINE" / "floating_brain" / "cuda" / "bin" / "fb_server.exe"),
                "9700", "fb_kernels.cubin", "index.html"],
    },
    9782: {
        "name": "routerfail", "signature": "routerfail.py",
        "cwd": SUB / "routerfail",
        "cmd": [PYTHON, "routerfail.py"],
    },
}


def probe(port: int, timeout: float = 5.0) -> dict:
    url = f"http://127.0.0.1:{port}/"
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(64)
            return {"ok": True, "status": r.status, "ms": round((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {"ok": True, "status": e.code, "ms": round((time.time() - t0) * 1000),
                "note": "reachable; non-2xx is normal for API-only services"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "error": type(e).__name__,
                "ms": round((time.time() - t0) * 1000)}


def listeners(port: int) -> list[dict]:
    out = []
    for c in psutil.net_connections(kind="tcp"):
        if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port and c.pid:
            try:
                p = psutil.Process(c.pid)
                out.append({
                    "pid": c.pid,
                    "cmdline": " ".join(p.cmdline()),
                    "cpu_s": p.cpu_times().user + p.cpu_times().system,
                    "rss_mb": round(p.memory_info().rss / 1e6, 1),
                    "threads": p.num_threads(),
                    "create_time": p.create_time(),
                    "ppid": p.ppid(),
                })
            except Exception:  # noqa: BLE001
                continue
    return out


def matches(entry: dict, signature: str) -> bool:
    return signature.lower() in (entry.get("cmdline") or "").lower()


def start(spec: dict) -> dict:
    log_dir = ROOT / "LOGS"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{spec['name']}-supervise.log"
    fh = open(log_path, "ab")
    try:
        p = subprocess.Popen(
            spec["cmd"], cwd=str(spec["cwd"]), stdout=fh, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {"pid": p.pid, "log": str(log_path)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "log": str(log_path)}
    finally:
        fh.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--keep", type=int, default=0, help="explicit keeper PID")
    ap.add_argument("--restart", action="store_true",
                    help="kill every matching listener and start one fresh instance")
    args = ap.parse_args()
    spec = SPECS.get(args.port)
    if not spec:
        print(f"no spec for port {args.port}")
        return 2

    before = listeners(args.port)
    matches_before = [e for e in before if matches(e, spec["signature"])]
    pre = probe(args.port)
    print(f"{spec['name']} :{args.port} listeners={len(before)} matching={len(matches_before)} "
          f"probe={pre.get('status') or pre.get('error')}")
    for e in sorted(matches_before, key=lambda x: -x["cpu_s"]):
        print(f"  pid={e['pid']:<6} cpu={e['cpu_s']:>8.1f}s rss={e['rss_mb']:>7.1f}MB "
              f"threads={e['threads']:>2} {e['cmdline'][:80]}")

    if not matches_before:
        print("no matching listener; nothing to reduce")
        return 0

    if args.restart:
        keeper = None
        victims = list(matches_before)
    else:
        keeper = (next((e for e in matches_before if e["pid"] == args.keep), None)
                  if args.keep else max(matches_before, key=lambda x: (x["cpu_s"], x["create_time"])))
        victims = [e for e in matches_before if e["pid"] != keeper["pid"]]
    print(f"keeper={keeper['pid'] if keeper else None} victims={len(victims)}")

    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "port": args.port, "service": spec["name"],
        "before": {"listeners": len(before), "matching": len(matches_before), "probe": pre},
        "keeper": keeper, "victims": victims, "applied": False,
    }

    if args.apply:
        killed = []
        for v in victims:
            try:
                psutil.Process(v["pid"]).terminate()
                killed.append({"pid": v["pid"], "result": "terminate"})
            except Exception as e:  # noqa: BLE001
                killed.append({"pid": v["pid"], "result": f"error:{type(e).__name__}"})
        time.sleep(3)
        for entry in killed:
            try:
                p = psutil.Process(entry["pid"])
                if p.is_running():
                    p.kill()
                    entry["result"] = "killed"
            except Exception:
                entry["result"] = "exited"
        record["killed"] = killed

        after = probe(args.port)
        started = None
        if not after["ok"]:
            started = start(spec)
            deadline = time.time() + 25
            while time.time() < deadline:
                time.sleep(2)
                after = probe(args.port, timeout=4.0)
                if after["ok"]:
                    break
        record["after"] = after
        record["started"] = started
        record["applied"] = True
        print(f"after: probe={after.get('status') or after.get('error')} started={started}")

    if OUT.exists():
        try:
            hist = json.loads(OUT.read_text(encoding="utf-8"))
            if not isinstance(hist, list):
                hist = [hist]
        except Exception:  # noqa: BLE001
            hist = []
    else:
        hist = []
    hist.append(record)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    if not args.apply:
        print("DRY RUN. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
