"""fix_ops_monitor_headless.py - the warden itself was opening windows every 30 s.

`ops_monitor.py` runs under `pythonw.exe` and shells out twice per tick:

    line ~89   nvidia-smi  (gpu())
    line ~142  powershell  (proc_table())

Neither passed CREATE_NO_WINDOW, so on this host each call is a console child of
a console-less parent - a window. The monitor ticks every 30 s, so the "no
windows" symptom would return forever even after every service was fixed.

(The supervisor's spawn already used CREATE_NO_WINDOW, and `services._ps_json`
already did too; the monitor was the last live site.)

Both calls now go through abrasax.winproc, which is the single rule.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\ops_monitor.py")

IMPORT_OLD = '''from abrasax import services  # noqa: E402
'''
IMPORT_NEW = '''from abrasax import services  # noqa: E402
from abrasax import winproc  # noqa: E402
'''

GPU_OLD = '''        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()'''
GPU_NEW = '''        # winproc: this file runs under pythonw, and a console child of a
        # console-less parent is a window (every 30 s, forever).
        out = winproc.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    before = src
    for old, new in ((IMPORT_OLD, IMPORT_NEW), (GPU_OLD, GPU_NEW)):
        if new in src:
            continue
        if src.count(old) != 1:
            raise SystemExit(f"anchor {src.count(old)}x: {old[:60]!r}")
        src = src.replace(old, new, 1)

    # any remaining raw subprocess.run of a console binary in this file
    if "subprocess.run(" in src:
        lines = [ln for ln in src.splitlines() if "subprocess.run(" in ln]
        raise SystemExit("raw subprocess.run still present: " + " | ".join(lines))

    if src != before:
        TARGET.write_text(src, encoding="utf-8", newline="")
        print("patched", TARGET)
    else:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
