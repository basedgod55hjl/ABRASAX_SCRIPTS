"""Launch the overlay and prove it STAYS up, not just that it starts.

The overlay has been dying repeatedly and each time the watchdog silently
resurrected it, which hid the cause. This runs it with output captured to a file
and checks it is still alive after N seconds -- so a crash inside the first
minute surfaces as a failure instead of a mystery.
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
PY = ROOT / "PYTHON/.venv_gui/Scripts/python.exe"
LOG = ROOT / "LOGS/overlay-soak.log"
ERR = ROOT / "LOGS/overlay-soak.err"
SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 45


def health() -> dict | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:9627/health", timeout=5) as r:
            import json
            return json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        return None


with LOG.open("w", encoding="utf-8") as fo, ERR.open("w", encoding="utf-8") as fe:
    p = subprocess.Popen(
        [str(PY), "ENGINE/floating_brain/imgui_overlay.py",
         "--width", "760", "--height", "760", "--topmost"],
        cwd=str(ROOT), stdout=fo, stderr=fe,
    )
    print(f"pid {p.pid}; watching for {SECONDS}s", flush=True)
    t0 = time.time()
    samples = []
    while time.time() - t0 < SECONDS:
        time.sleep(5)
        rc = p.poll()
        h = health()
        alive = rc is None
        samples.append((round(time.time() - t0, 1), alive, rc,
                        h.get("frames") if h else None,
                        round(h.get("fps", 0), 1) if h else None))
        print(f"  t+{samples[-1][0]:5.1f}s alive={alive} rc={rc} "
              f"frames={samples[-1][3]} fps={samples[-1][4]}", flush=True)
        if not alive:
            break
    final = p.poll()
    if final is None:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()

print(f"\nresult: {'SURVIVED' if final is None else f'DIED rc={final}'}")
if final is not None:
    txt = ERR.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    print("stderr tail:")
    for ln in txt[-12:]:
        print("   ", ln)
sys.exit(0 if final is None else 1)
