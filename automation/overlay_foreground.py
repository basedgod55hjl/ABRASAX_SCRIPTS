"""Launch the overlay for N seconds and report exactly how it died.

Redirecting stdout to a file via Start-Process can leave a half-written tail;
this waits on the process, then reports exit code, stdout tail and stderr head
so a crash is never mistaken for a clean close.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
PY = ROOT / "PYTHON/.venv_gui/Scripts/python.exe"
SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 45
out = ROOT / "LOGS/overlay-fg.log"
err = ROOT / "LOGS/overlay-fg.err"

print(f"launching overlay for {SECONDS}s")
t0 = time.time()
with out.open("w", encoding="utf-8") as fo, err.open("w", encoding="utf-8") as fe:
    p = subprocess.Popen(
        [str(PY), "ENGINE/floating_brain/imgui_overlay.py",
         "--width", "760", "--height", "760", "--topmost"],
        cwd=str(ROOT), stdout=fo, stderr=fe,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    try:
        rc = p.wait(timeout=SECONDS)
        died_early = True
    except subprocess.TimeoutExpired:
        died_early = False
        rc = None
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
elapsed = time.time() - t0

lines = out.read_text(encoding="utf-8", errors="replace").splitlines()
errlines = err.read_text(encoding="utf-8", errors="replace").splitlines()

print(f"alive {elapsed:.1f}s  exited_early={died_early}  rc={rc}  stdout_lines={len(lines)}")
print("--- stdout tail ---")
for ln in lines[-6:]:
    print(" ", ln)
print("--- stderr (first 25) ---")
for ln in errlines[:25]:
    print(" ", ln)
if died_early:
    frames = [ln for ln in lines if "frame " in ln]
    print(f"DIED AT FRAME LINE: {frames[-1] if frames else 'none'}")
sys.exit(0 if not died_early else 1)
