"""_probe_visible_consoles.py - which processes, if any, own a VISIBLE console window?

Answers the operator's question directly: when the stack is running, does
anything put a black window on the desktop? Enumerates every window of class
ConsoleWindowClass that is visible, maps the owning PID to a process name and
command line, and writes LOGS/visible-consoles.json.

    python SCRIPTS/_probe_visible_consoles.py           # also prints
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "LOGS" / "visible-consoles.json"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def _cmdlines() -> dict[int, str]:
    try:
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine "
             "| ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rows = json.loads(cp.stdout or "[]")
    except Exception:
        return {}
    return {int(r["ProcessId"]): f"{r.get('Name')} :: {(r.get('CommandLine') or '')[:140]}"
            for r in rows if r.get("ProcessId")}


def main() -> int:
    found: list[dict] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _cb(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, buf, 128)
        if buf.value != "ConsoleWindowClass":
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        found.append({"hwnd": int(hwnd or 0), "pid": int(pid.value),
                      "title": title.value})
        return True

    user32.EnumWindows(_cb, 0)
    names = _cmdlines()
    for row in found:
        row["process"] = names.get(row["pid"], "<gone>")
    payload = {
        "count": len(found),
        "stack_processes": [r for r in found
                            if any(k in (r.get("process") or "").lower()
                                   for k in ("lms", "lmstudio", "llama", "node",
                                             "powershell", "pythonw", "cmd.exe"))],
        "all": found,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
