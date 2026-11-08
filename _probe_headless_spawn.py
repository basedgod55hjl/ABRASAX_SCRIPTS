"""_probe_headless_spawn.py - does a spawned console child get its own window?

Counting ConsoleWindowClass windows desktop-wide was too noisy: other agents on
this box start and stop consoles while the probe runs, and one run even reported
the safe flag as the one that added a window (measured 2026-11-01, both
directions seen). Global counts cannot answer this question.

Ask the child instead. It writes its own console handle and that window's
visibility to a file (never stdout - piped stdio is exactly what stops Windows
from allocating a console, which is what made the first version of this probe
read 0 for both cases):

    python -c "hwnd = GetConsoleWindow(); IsWindowVisible(hwnd) -> file"

Run under pythonw, as the runtime does:

    pythonw.exe SCRIPTS\\_probe_headless_spawn.py

Result -> LOGS/headless-spawn.json (pythonw has no stdout).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abrasax import winproc  # noqa: E402

OUT = ROOT / "LOGS" / "headless-spawn.json"

CHILD_CODE = r"""
import ctypes, json, sys
k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
hwnd = int(k32.GetConsoleWindow() or 0)
open(sys.argv[1], "w").write(json.dumps({
    "hwnd": hwnd,
    "visible": bool(hwnd and u32.IsWindowVisible(hwnd)),
}))
"""


def probe(flags: int) -> dict:
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "child.json"
        proc = subprocess.Popen([sys.executable, "-c", CHILD_CODE, str(report)],
                                creationflags=flags,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"error": "timeout"}
        time.sleep(0.3)
        try:
            return json.loads(report.read_text(encoding="utf-8"))
        except OSError:
            return {"error": "child wrote no report"}


def main() -> int:
    parent = 0
    try:
        import ctypes
        parent = int(ctypes.windll.kernel32.GetConsoleWindow() or 0)
    except Exception:
        pass
    result = {
        "parent_console": parent,
        "no_flag": probe(0),
        "create_no_window": probe(winproc.CREATE_NO_WINDOW),
        "via_winproc_run": None,
        "note": "visible=true means the child opened a console window",
    }
    # And the helper the runtime actually uses, with stdio inherited.
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "child.json"
        winproc.run([sys.executable, "-c", CHILD_CODE, str(report)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        try:
            result["via_winproc_run"] = json.loads(report.read_text(encoding="utf-8"))
        except OSError:
            pass
    result["ok"] = (bool(result["no_flag"].get("visible"))
                    and not result["create_no_window"].get("visible")
                    and not (result["via_winproc_run"] or {}).get("visible"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
