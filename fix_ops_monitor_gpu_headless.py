"""fix_ops_monitor_gpu_headless.py - gpu() still ran nvidia-smi raw.

The earlier attempt refused to write while any raw call remained (a good guard)
and so left gpu() untouched. Patch it exactly, then verify from disk in the same
process before claiming success.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\ops_monitor.py")

OLD = '''    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()'''
NEW = '''    try:
        # winproc: ops_monitor runs under pythonw and ticks every 30 s; a raw
        # console child here is a console window every 30 s, forever.
        out = winproc.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW in src:
        print("already applied")
    else:
        if src.count(OLD) != 1:
            raise SystemExit(f"anchor {src.count(OLD)}x")
        TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8", newline="")
        print("patched", TARGET)

    on_disk = TARGET.read_text(encoding="utf-8")
    raw = [n for n, ln in enumerate(on_disk.splitlines(), 1)
           if "subprocess.run(" in ln]
    print("raw subprocess.run lines on disk:", raw or "none")
    print("winproc.run count:", on_disk.count("winproc.run("))
    return 0 if not raw and on_disk.count("winproc.run(") == 2 else 1


if __name__ == "__main__":
    sys.exit(main())
