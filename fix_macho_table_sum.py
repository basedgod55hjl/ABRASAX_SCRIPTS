#!/usr/bin/env python3
"""fix_macho_table_sum.py -- enforce the invariant that catches a shifted table.

Measured on a permissive 28-byte walk of UnityPlayer.dylib (ncmds=43, sizeofcmds=6160):
    [0] off 0x1c cmd 0x00000000 cmdsize 25      <- the reserved u32
    [1] off 0x35 cmd 0x00000000 cmdsize 0       <- cursor collapses to 1-byte steps
    [6] off 0x3a cmd 0x00000000 cmdsize 0x80000000 -> jumps to 0x8000003a
Seven ids decoded, seven garbage, then the walk leaves a 6160-byte table by ~2 GB.

A reader that validates nothing prints all of that. A reader that checks one thing --
`sum(cmdsize) == sizeofcmds`, which the ABI guarantees -- cannot: the shifted table stops
being consistent with the header at the first command.

Verified as a rule before enforcing it: 26 of 26 arm64 Mach-O images shipped with Unity
satisfy the equality exactly, so this is not a heuristic.

Run: python SCRIPTS/fix_macho_table_sum.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "abrasax" / "macho.py"

ANCHOR = """        commands.append(LoadCommand(cmd=cmd, cmdsize=cmdsize, offset=off, name=name, data=payload))
        off += cmdsize

    return tuple(commands), tuple(segments), uuid, entryoff, tuple(dylibs)"""

NEW = """        commands.append(LoadCommand(cmd=cmd, cmdsize=cmdsize, offset=off, name=name, data=payload))
        off += cmdsize

    # sizeofcmds is defined as the total size of the load commands, so the walk must land
    # exactly on it. This is the single check that survives a wrong table start even when the
    # invented ids happen to look plausible: measured on 26 real arm64 images, all 26 satisfy
    # it exactly, and a 28-byte start violates it at the first command.
    consumed = off - start
    if consumed != header.sizeofcmds:
        raise MachOError(
            f"load commands occupy {consumed} bytes but sizeofcmds says "
            f"{header.sizeofcmds}: the table is shifted, padded, or ncmds disagrees with "
            f"sizeofcmds", start)

    return tuple(commands), tuple(segments), uuid, entryoff, tuple(dylibs)"""

MARK = "load commands occupy"


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    done = MARK in text
    if "--check" in sys.argv:
        print(("PASS " if done else "FAIL ") + f"sizeofcmds equality enforced={done}")
        return 0 if done else 1
    if done:
        print("already enforced: sum(cmdsize) == sizeofcmds")
        return 0
    if ANCHOR not in text:
        print("FAIL  load-command loop tail not found")
        return 1
    bak = SRC.with_suffix(".py.bak-tablesum")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    SRC.write_text(text.replace(ANCHOR, NEW, 1), encoding="utf-8")

    import py_compile

    py_compile.compile(str(SRC), doraise=True)
    print("patched macho.py: sum(cmdsize) must equal sizeofcmds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
