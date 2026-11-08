"""fix_ops_monitor_headless_proctable.py - the second raw call in the warden.

fix_ops_monitor_headless.py refused to declare success while one
`subprocess.run` remained: proc_table()'s PowerShell query. Same rule, same
helper. The guard in the previous script stays (it is why this was not missed).

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\ops_monitor.py")

OLD = '''        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=25,
        ).stdout'''
NEW = '''        out = winproc.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=25,
        ).stdout'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW in src:
        print("already applied")
    else:
        if src.count(OLD) != 1:
            raise SystemExit(f"anchor {src.count(OLD)}x")
        src = src.replace(OLD, NEW, 1)
        TARGET.write_text(src, encoding="utf-8", newline="")
        print("patched", TARGET)
    left = [ln for ln in TARGET.read_text(encoding="utf-8").splitlines()
            if "subprocess.run(" in ln]
    if left:
        raise SystemExit("raw calls remain: " + " | ".join(left))
    print("no raw subprocess.run left in ops_monitor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
