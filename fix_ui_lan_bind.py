#!/usr/bin/env python3
"""fix_ui_lan_bind.py -- the other watchdog was resurrecting the UI on loopback.

`C:\\vlc-build\\resurrect_watchdog.py` ("NO ONE DIES") relaunches a fixed list of roles
every 60 s with hardcoded command lines. Its ui-http role carries
    -m http.server 8090 --bind 127.0.0.1 --directory UI\\abrasax-ui\\web
so whichever watchdog wins the race decides the bind. After the supervisor was pointed at
0.0.0.0, that process was observed re-spawning the loopback server (pid 20856), which means
the phone could reach the gateway and not the page.

Killing another agent's watchdog is not this script's job. It aligns the one line that
disagrees, so both launchers now mean the same thing.

Run: python SCRIPTS/fix_ui_lan_bind.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

WATCHDOG = Path(r"C:\vlc-build\resurrect_watchdog.py")
OLD = '["-m", "http.server", "8090", "--bind", "127.0.0.1", "--directory", r"UI\\abrasax-ui\\web"]'
NEW = '["-m", "http.server", "8090", "--bind", "0.0.0.0", "--directory", r"UI\\abrasax-ui\\web"]'


def main() -> int:
    if not WATCHDOG.exists():
        print(f"SKIP  {WATCHDOG} not on this host")
        return 0
    text = WATCHDOG.read_text(encoding="utf-8", errors="replace")
    applied = '"--bind", "0.0.0.0"' in text
    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"watchdog ui bind=0.0.0.0 ({applied})")
        return 0 if applied else 1
    if applied:
        print("already aligned: resurrect_watchdog ui-http")
        return 0
    if OLD not in text:
        print("FAIL  ui-http role line not found")
        return 1
    bak = WATCHDOG.with_suffix(".py.bak-lanbind")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    WATCHDOG.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("aligned resurrect_watchdog.py: ui-http -> 0.0.0.0:8090")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
