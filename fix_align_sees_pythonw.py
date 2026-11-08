"""fix_align_sees_pythonw.py -- align was blind to every supervisor-launched role.

`get_procs()` enumerated pids with

    tasklist /FI "IMAGENAME eq python.exe"
    for exe in ("node.exe", "llama-server.exe")

and never asked for **pythonw.exe** -- which is exactly what the supervisor uses
for services (measured 2026-11-01: jev-fused runs as pythonw 42552 -> 41664 and
read as "-- jev-fused 0", i.e. absent). Any role started by the supervisor was
invisible to the audit.

Also: a role inside its documented allowance still printed "!!" (three term.mjs
consoles), even though it no longer produces a DUPLICATE_ROLE finding.

Idempotent. Backs up to abrasax_align.py.bak-pythonw-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\abrasax_align.py")

OLD_EXE = '    for exe in ("node.exe", "llama-server.exe"):'
NEW_EXE = ('    # pythonw.exe matters: the supervisor launches every service with it,\n'
           '    # so without this the audit reports those roles as absent ("0").\n'
           '    for exe in ("pythonw.exe", "node.exe", "llama-server.exe"):')

OLD_MARK = '        mark = "OK " if len(hits) == 1 else ("-- " if not hits else "!! ")'
NEW_MARK = ('        allowed = ALLOWED_EXTRA.get(role, 1)\n'
            '        if len(hits) <= allowed and hits:\n'
            '            mark = "OK "\n'
            '        else:\n'
            '            mark = "-- " if not hits else "!! "')


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if '"pythonw.exe", "node.exe"' in src and "allowed = ALLOWED_EXTRA.get(role, 1)" in src:
        print("already patched")
        return 0
    for needle in (OLD_EXE, OLD_MARK):
        if needle not in src:
            print(f"ANCHOR NOT FOUND: {needle.strip()[:60]!r} -- refusing to guess")
            return 1
    bak = TARGET.with_suffix(".py.bak-pythonw-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    TARGET.write_text(src.replace(OLD_EXE, NEW_EXE, 1).replace(OLD_MARK, NEW_MARK, 1),
                      encoding="utf-8")
    print(f"patched {TARGET.name} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
