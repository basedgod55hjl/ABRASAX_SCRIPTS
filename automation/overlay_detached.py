"""Detach the overlay so it survives the launching shell.

Findings so far:
  * foreground + real file handles  -> alive 45s / 3180 frames
  * Start-Process + redirection     -> dies silently around frame 660
The difference is the stdout pipe being closed under the child. Give the child
a durable log file via cmd redirection and CREATE_NEW_PROCESS_GROUP +
DETACHED_PROCESS so nothing it writes can fail with EINVAL and kill it.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
PYW = ROOT / "PYTHON/.venv_gui/Scripts/pythonw.exe"
LOG = ROOT / "LOGS/overlay-detached.log"
ERR = ROOT / "LOGS/overlay-detached.err"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

cmd = (
    f'"{PYW}" "ENGINE\\floating_brain\\imgui_overlay.py" '
    f'--width 760 --height 760 --topmost '
    f'> "{LOG}" 2> "{ERR}"'
)
p = subprocess.Popen(
    cmd, cwd=str(ROOT), shell=True,
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    close_fds=True,
)
print(f"launcher pid {p.pid}")
time.sleep(18)

out = LOG.read_text(encoding="utf-8", errors="replace").splitlines() if LOG.exists() else []
frames = [ln for ln in out if "frame " in ln]
print(f"frames logged: {len(frames)}  last: {frames[-1] if frames else 'none'}")

q = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
     "Where-Object { $_.CommandLine -match 'imgui_overlay' } | "
     "ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }"],
    capture_output=True, text=True, timeout=30,
)
alive = [ln for ln in q.stdout.splitlines() if ln.strip()]
print(f"alive overlay processes: {len(alive)}")
for ln in alive:
    print("  ", ln[:130])
sys.exit(0 if alive else 1)
