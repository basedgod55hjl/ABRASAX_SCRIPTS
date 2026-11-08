"""Non-stop UI improvement loop.

Every cycle: capture the live HUD -> measure it deterministically ->
ask the locally-served Unity GGUF for 3 concrete changes -> append to the
improvement log and the ledger -> /activity shows it on the HUD.

Runs until killed. Each cycle is idempotent and leaves a timestamped record, so
a crash loses at most one cycle.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
PY = ROOT / "PYTHON/.venv_gui/Scripts/python.exe"
LOG = ROOT / "LOGS/ui-improve-loop.log"
HIST = ROOT / "DATA/runtime-memory/ui_improvements.jsonl"
HEALTH = "http://127.0.0.1:9627/health"


def run(script: Path, timeout: int = 300) -> tuple[int, str]:
    try:
        r = subprocess.run([str(PY), str(script)], capture_output=True,
                           text=True, timeout=timeout, cwd=str(ROOT))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.SubprocessError as exc:
        return -1, repr(exc)


def overlay_ok() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(HEALTH, timeout=5) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    cycle = 0
    while True:
        cycle += 1
        t0 = time.time()
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        alive = overlay_ok()
        rc_cap, out_cap = run(ROOT / "SCRIPTS/automation/capture_overlay.py")
        rc_imp, out_imp = run(ROOT / "ENGINE/floating_brain/unity_improve.py")
        row = {
            "cycle": cycle, "ts": stamp, "overlay_up": alive,
            "capture_rc": rc_cap, "improve_rc": rc_imp,
            "seconds": round(time.time() - t0, 1),
            "tail": out_imp.strip().splitlines()[-1:] ,
        }
        HIST.parent.mkdir(parents=True, exist_ok=True)
        with HIST.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"\n===== cycle {cycle} {stamp} overlay={alive} "
                     f"cap={rc_cap} imp={rc_imp} {row['seconds']}s =====\n")
            fh.write(out_imp[-1500:])
        time.sleep(max(5, interval))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
