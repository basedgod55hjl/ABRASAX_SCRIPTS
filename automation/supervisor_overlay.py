"""Register the overlay in supervisor AUTOSTART so it is actually repaired.

_start_service() already launches with CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP and real file handles, which is exactly the launch
mode the overlay survives under (Start-Process redirection killed it at ~660
frames). So the supervisor is the correct owner of this process.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\SCRIPTS\automation\supervisor.py")
src = P.read_text(encoding="utf-8")

if '"floating-brain-overlay"' in src:
    sys.exit("already registered")

anchor = '''    "abrasax-brain": {
        "cmd": [sys.executable, "-m", "abrasax.brain", "serve", "--port", "9626"],
        "cwd": ROOT,
    },'''
if anchor not in src:
    sys.exit("anchor not found")

replacement = anchor + '''
    "floating-brain-overlay": {
        # The HUD itself. It exposes /health on 9627 precisely so this watchdog
        # can see it: measured 2026-10-18 it was dying with nobody noticing
        # because supervisor.tick() skips any service without a port.
        "cmd": [sys.executable, "ENGINE/floating_brain/imgui_overlay.py",
                "--width", "760", "--height", "760", "--topmost"],
        "cwd": ROOT,
    },'''

P.write_text(src.replace(anchor, replacement, 1), encoding="utf-8")
print("supervisor: floating-brain-overlay added to AUTOSTART")
