"""Live UI wiring: hot-restart the overlay when its source changes, and apply
layout edits without restarting at all.

TWO DIFFERENT KINDS OF "UPDATE", DELIBERATELY TREATED DIFFERENTLY
----------------------------------------------------------------
1. LAYOUT EDIT  (DATA/runtime-memory/ui_layout.json)
   The overlay itself watches this file and re-applies anchor/offset/size every
   time it changes. No restart, no frame lost, no flicker. "Just rearranges."
   The lever is anchor+offset, because PanelManager recomputes each panel's
   position from those every frame -- writing `pos` would be overwritten by the
   spring on the next tick.

2. SOURCE EDIT  (imgui_overlay.py / panels.py / brain3d.py)
   Python cannot reload a running GL context safely, so this must restart the
   process. A restart is only allowed if the new file parses; a half-written
   edit (which has bitten this repo repeatedly) must never take the UI down.
   Backoff prevents a crash-loop from spawning processes forever.

The watcher is a single loop, not a cron: it owns at most one overlay instance
and refuses to start a second (the duplicate-instance problem measured earlier).
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(r"C:\ABRASAX")
ENGINE = ROOT / "ENGINE" / "floating_brain"
LAYOUT = ROOT / "DATA" / "runtime-memory" / "ui_layout.json"
LOG = ROOT / "LOGS" / "ui_hotwire.log"
PYW = ROOT / "PYTHON" / ".venv_gui" / "Scripts" / "pythonw.exe"

WATCHED = [ENGINE / "imgui_overlay.py", ENGINE / "panels.py", ENGINE / "brain3d.py"]
ARGS = ["ENGINE/floating_brain/imgui_overlay.py", "--width", "760",
        "--height", "760", "--topmost", "--borderless"]

POLL_S = 1.0
MIN_RESTART_GAP_S = 8.0     # backoff so a syntax error cannot spin processes


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def digest(p: pathlib.Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return "-"


def parses(p: pathlib.Path) -> tuple[bool, str]:
    try:
        ast.parse(p.read_bytes(), filename=str(p))
        return True, ""
    except SyntaxError as exc:
        return False, f"line {exc.lineno}: {exc.msg}"
    except (ValueError, OSError) as exc:
        return False, repr(exc)[:120]


def overlay_pids() -> list[int]:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
             "'*imgui_overlay*' } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=20)
        return [int(x) for x in r.stdout.split() if x.strip().isdigit()]
    except Exception:  # noqa: BLE001
        return []


def stop_overlay() -> None:
    pids = overlay_pids()
    if not pids:
        return
    args = ",".join(str(p) for p in pids)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"{args} | ForEach-Object {{ Stop-Process -Id $_ -Force "
                    f"-ErrorAction SilentlyContinue }}"],
                   capture_output=True, timeout=30)
    log(f"stopped overlay pids {pids}")


def start_overlay() -> int | None:
    try:
        p = subprocess.Popen([str(PYW), *ARGS], cwd=str(ROOT),
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=0x00000008 | 0x08000000, close_fds=True)
        log(f"started overlay pid {p.pid}")
        return p.pid
    except Exception as exc:  # noqa: BLE001
        log(f"start FAILED: {exc!r}")
        return None


def main() -> int:
    log("hotwire start")
    state = {p.name: digest(p) for p in WATCHED}
    layout_digest = digest(LAYOUT)
    last_restart = 0.0

    while True:
        time.sleep(POLL_S)

        # layout edits: the overlay applies these itself, so only note them
        d = digest(LAYOUT)
        if d != layout_digest:
            layout_digest = d
            log(f"layout changed ({d}) - overlay applies it live, no restart")

        changed = [p for p in WATCHED if digest(p) != state.get(p.name)]
        if not changed:
            continue

        # every changed file must parse before we take the UI down
        bad = []
        for p in changed:
            ok, why = parses(p)
            if not ok:
                bad.append(f"{p.name} {why}")
        if bad:
            for p in changed:      # adopt the new digest anyway, so we don't
                state[p.name] = digest(p)   # re-log the same failure each tick
            log("REFUSED restart, unparseable: " + "; ".join(bad))
            continue

        now = time.time()
        if now - last_restart < MIN_RESTART_GAP_S:
            log(f"edit to {[p.name for p in changed]} but backing off "
                f"({now - last_restart:.1f}s < {MIN_RESTART_GAP_S}s)")
            for p in changed:
                state[p.name] = digest(p)
            continue

        for p in changed:
            state[p.name] = digest(p)
        log("reload: " + ", ".join(p.name for p in changed))
        stop_overlay()
        time.sleep(1.5)
        start_overlay()
        last_restart = now


if __name__ == "__main__":
    raise SystemExit(main())
