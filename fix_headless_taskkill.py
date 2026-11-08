"""fix_headless_taskkill.py - taskkill is a console app too; hide it.

`tools/llamacpp_serve.py --stop` calls taskkill twice. From `pythonw.exe` that
is a console child without CREATE_NO_WINDOW, i.e. a window flash on every stop.
Same rule as the rest of the run: everything through abrasax.winproc.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\tools\llamacpp_serve.py")

PATCHES = [
    ('        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)',
     '        winproc.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)'),
    ('            subprocess.run(["taskkill", "/PID", line.strip(), "/F"], capture_output=True)',
     '            winproc.run(["taskkill", "/PID", line.strip(), "/F"], capture_output=True)'),
]


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    before = src
    for old, new in PATCHES:
        if new in src:
            continue
        if src.count(old) != 1:
            raise SystemExit(f"anchor {src.count(old)}x: {old[:60]!r}")
        src = src.replace(old, new, 1)
    if src != before:
        TARGET.write_text(src, encoding="utf-8", newline="")
        print("patched", TARGET)
    else:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
