#!/usr/bin/env python3
"""fix_adb_discovery.py -- find the adb this host actually has.

`abrasax.adb_sensors.find_adb()` resolves ABRASAX_ADB, then PATH, then ADB_CANDIDATES.
On this host none of the candidates existed (they name `sirch`'s SDK and C:\\platform-tools)
and adb was not on PATH, so every sense reported "disconnected" while the phone was plugged
in and authorised. platform-tools 37.0.1 is now installed in-tree at
C:\\abrasax\\TOOLS\\platform-tools, which is the one place a checkout can rely on.

Adds the repo-local binary (and the standard per-user SDK path this host lacks) to the
candidate list, first.

Run: python SCRIPTS/fix_adb_discovery.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "abrasax" / "adb_sensors.py"

OLD = """ADB_CANDIDATES = (
    # DEAD PATH (sirch): C:\\Users\\sirch\\Android\\platform-tools\\adb.exe has no local equivalent on this host.
    str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"),
    r"C:\\platform-tools\\adb.exe","""

NEW = """ADB_CANDIDATES = (
    # In-tree install (this host): platform-tools 37.0.1 unpacked into the repo, so a
    # checkout carries its own adb instead of depending on a user SDK that may not exist.
    str(Path(__file__).resolve().parent.parent / "TOOLS" / "platform-tools" / "adb.exe"),
    # DEAD PATH (sirch): C:\\Users\\sirch\\Android\\platform-tools\\adb.exe has no local equivalent on this host.
    str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"),
    r"C:\\platform-tools\\adb.exe","""

MARK = "In-tree install (this host)"


def main() -> int:
    text = SRC.read_text(encoding="utf-8-sig")
    applied = MARK in text
    if "--check" in sys.argv:
        ok = applied and (SRC.parent.parent / "TOOLS" / "platform-tools" / "adb.exe").exists()
        print(("PASS " if ok else "FAIL ") + f"adb discovery in-tree={applied} binary_exists={ok}")
        return 0 if ok else 1
    if applied:
        print("already patched: adb candidates")
        return 0
    if OLD not in text:
        print("FAIL  ADB_CANDIDATES anchor not found")
        return 1
    bak = SRC.with_suffix(".py.bak-adbpath")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    SRC.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched ADB_CANDIDATES: repo-local platform-tools first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
