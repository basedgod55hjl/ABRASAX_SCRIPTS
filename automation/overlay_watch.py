"""Launch the overlay as a child and record HOW it died, with an exit code.

The overlay's own diagnostics (LOGS/overlay-exit.log) cover every Python-level
exit path: ESC, WM_CLOSE, uncaught exception, normal return. But the observed
deaths leave only "main() start" and nothing else -- no Python exit path ran.

That leaves two possibilities Python cannot report:
  * a hard kill (TerminateProcess) -- no interpreter cleanup at all
  * a C-level fault in the GL/CUDA driver -- the process dies inside a native
    frame, so traceback/excepthook/finally never execute

Both are distinguishable by the child's exit code, which Windows preserves for
the parent. This wrapper is the only place that code can be read, because once
the process is gone it is gone.

Exit code meanings:
   0x00000000        clean return from main()
   0xC0000005  (-1073741819)  access violation  -> native crash (GL/driver)
   0xC0000409  (-1073740791)  stack buffer overrun / __fastfail (GS check)
   0xC000013A  (-1073741510)  Ctrl-C / console close
   0x00000001  +/-1           Python SystemExit(1)
   0xFFFFFFFF  (-1)           TerminateProcess by another actor
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(r"C:\ABRASAX")
PY = ROOT / "PYTHON" / ".venv_gui" / "Scripts" / "python.exe"
OVERLAY = ROOT / "ENGINE" / "floating_brain" / "imgui_overlay.py"
LOG = ROOT / "LOGS" / "overlay-watch.jsonl"
HEALTH = "http://127.0.0.1:9627/health"

ARGS = ["--width", "760", "--height", "760", "--topmost"]

CODES = {
    0: "clean return from main()",
    0xC0000005: "ACCESS VIOLATION (native crash: GL/driver)",
    0xC0000409: "STACK BUFFER OVERRUN / __fastfail (GS check)",
    0xC000013A: "console close / Ctrl-C",
    0xC0000135: "DLL not found",
    0xC0000142: "DLL init failed",
    0xFFFFFFFF: "TerminateProcess (-1)",
}


def _health() -> dict:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def _log(rec: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
        fh.flush()


def run_once() -> dict:
    t0 = time.time()
    # CREATE_NO_WINDOW: the overlay is a GUI process; no console wanted.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.Popen([str(PY), str(OVERLAY), *ARGS],
                         cwd=str(ROOT), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags)
    last_health: dict = {}
    while p.poll() is None:
        time.sleep(1.0)
        h = _health()
        if h:
            last_health = h
    rc = p.returncode
    unsigned = rc & 0xFFFFFFFF if rc is not None else None
    rec = {
        "pid": p.pid,
        "rc_signed": rc,
        "rc_hex": f"0x{unsigned:08X}" if unsigned is not None else None,
        "meaning": CODES.get(unsigned, "unknown"),
        "seconds": round(time.time() - t0, 2),
        "frames_at_death": last_health.get("frames"),
        "fps_at_death": last_health.get("fps"),
    }
    _log(rec)
    return rec


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for i in range(n):
        rec = run_once()
        print(f"[{i + 1}/{n}] {rec['rc_hex']}  {rec['meaning']}  "
              f"{rec['seconds']}s  frames={rec['frames_at_death']}", flush=True)
        if i + 1 < n:
            time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
