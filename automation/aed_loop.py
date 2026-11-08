#!/usr/bin/env python3
"""AED — Autonomous Execution Daemon loop.

One bounded controller for the PC + phone build loop:
  1. enforce the single-GGUF residency policy,
  2. probe the service stack,
  3. build/install the APK only when the Android source hash changed,
  4. run the fast gateway/stream test gate every N ticks,
  5. append a JSON record and sleep.

Stop with:  echo stop > LOGS/aed_loop.stop
Usage:      python SCRIPTS/automation/aed_loop.py --once
            python SCRIPTS/automation/aed_loop.py --interval 300
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "LOGS" / "aed_loop.json"
LOG = ROOT / "LOGS" / "aed_loop.jsonl"
STOP = ROOT / "LOGS" / "aed_loop.stop"
PY = sys.executable


def run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def tick(iteration: int, tests_every: int) -> dict:
    rec: dict = {"ts": datetime.now(timezone.utc).isoformat(), "iteration": iteration}

    # 1. model residency
    rc, out = run([PY, str(ROOT / "SCRIPTS/automation/keep_model_loaded.py"), "--once"], timeout=300)
    rec["model_rc"] = rc
    rec["model"] = out.strip()[-400:]

    # 2. service probe
    rc, out = run([PY, str(ROOT / "probe_services.py")], timeout=180)
    alive = next((l for l in out.splitlines() if l.startswith("ALIVE:")), "")
    rec["services_rc"] = rc
    rec["services"] = alive
    rec["services_tail"] = out.strip()[-500:]

    # 3. build/install only on source change
    rc, out = run([PY, str(ROOT / "SCRIPTS/automation/apk_build_loop.py"), "--once"], timeout=1800)
    rec["build_rc"] = rc
    try:
        rec["build"] = json.loads(out[out.find("{"):out.rfind("}") + 1])
    except Exception:  # noqa: BLE001
        rec["build_raw"] = out.strip()[-600:]

    # 4. fast test gate
    if tests_every > 0 and iteration % tests_every == 0:
        rc, out = run([PY, "-m", "pytest",
                       "TESTS/python/test_gateway.py", "TESTS/python/test_stream.py",
                       "-q", "--tb=short", "-p", "no:cacheprovider"], timeout=900)
        rec["tests_rc"] = rc
        rec["tests"] = out.strip().splitlines()[-1] if out.strip() else ""
    else:
        rec["tests"] = "skipped (not this tick)"

    STATE.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--tests-every", type=int, default=5)
    args = ap.parse_args()
    i = 0
    while not STOP.exists():
        i += 1
        try:
            r = tick(i, args.tests_every)
            b = r.get("build") or {}
            print(f"{r['ts']} iter={i} services={r.get('services', '')} "
                  f"built={b.get('built')} installed={b.get('installed')} tests={r.get('tests')}",
                  flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"tick_error {type(exc).__name__}: {exc}", flush=True)
        if args.once:
            break
        time.sleep(max(60, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
