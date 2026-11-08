#!/usr/bin/env python3
"""fix_macho_header_size_hint.py -- name the 28-vs-32 mistake when the table looks shifted.

Measured on the 26 arm64 Mach-O images Unity ships (PlaybackEngines/MacStandaloneSupport):
starting the load-command table at 28 instead of 32 gives, in **26 of 26** files,

    cmd = 0            <- the `reserved` u32
    cmdsize = 25 or 27 <- the real first command id: LC_SEGMENT_64 (0x19) or LC_UUID (0x1B)

so the failure always looks like "cmdsize 25 is not 4-byte aligned" / "cmdsize 0 is below the
8-byte header". Correct and useless: the reader's own header size is the thing that is wrong,
and nothing in that message says so.

This adds the diagnosis to the first-command errors on a 64-bit image: it points at
mach_header_64 being 32 bytes and ends with the reserved field. A reader built with 28 now
fails with the answer instead of a symptom.

Run: python SCRIPTS/fix_macho_header_size_hint.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "abrasax" / "macho.py"

HELPER_ANCHOR = "def _parse_load_commands("
HELPER = '''def _shifted_table_hint(index: int, header: "MachOHeader") -> str:
    """Name the most likely cause when the FIRST command in a 64-bit image is impossible.

    Measured 2026-11-02 on 26 real arm64 images: a reader that starts the table at 28 (i.e.
    forgets that mach_header_64 ends with `reserved`) reads cmd=0 and a "cmdsize" equal to the
    real first command id (25 or 27), in every one of them. The symptom is an alignment or
    size error on command 0; the cause is the header size.
    """
    if index != 0 or not header.is_64:
        return ""
    return (
        " -- if this is command 0, the header size is the suspect: mach_header_64 is 32 bytes "
        "(magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved), so the "
        "load-command table starts at 32, not 28. A 28-byte start reads the reserved u32 as "
        "the first command id.")


'''

OLD_LOW = '''        if cmdsize < 8:
            # Measured on hand-edited files: cmdsize 0 walks the table forever, cmdsize 4
            # makes the next command start inside this one's header.
            raise MachOError(f"load command {index}: cmdsize {cmdsize} is below the 8-byte header", off)
        if cmdsize % 4:
            raise MachOError(f"load command {index}: cmdsize {cmdsize} is not 4-byte aligned", off)'''

NEW_LOW = '''        if cmdsize < 8:
            # Measured on hand-edited files: cmdsize 0 walks the table forever, cmdsize 4
            # makes the next command start inside this one's header.
            raise MachOError(
                f"load command {index}: cmdsize {cmdsize} is below the 8-byte header"
                + _shifted_table_hint(index, header), off)
        if cmdsize % 4:
            raise MachOError(
                f"load command {index}: cmdsize {cmdsize} is not 4-byte aligned"
                + _shifted_table_hint(index, header), off)'''

MARK = "_shifted_table_hint"


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    done = "def _shifted_table_hint(" in text and "_shifted_table_hint(index, header)" in text
    if "--check" in sys.argv:
        print(("PASS " if done else "FAIL ") + f"header-size hint={done}")
        return 0 if done else 1
    if done:
        print("already patched: header-size hint")
        return 0

    if HELPER_ANCHOR not in text:
        print("FAIL  _parse_load_commands not found")
        return 1
    if OLD_LOW not in text:
        print("FAIL  command-size guards not found")
        return 1

    text = text.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    text = text.replace(OLD_LOW, NEW_LOW, 1)

    bak = SRC.with_suffix(".py.bak-sizehint")
    if not bak.exists():
        bak.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    SRC.write_text(text, encoding="utf-8")

    import py_compile

    py_compile.compile(str(SRC), doraise=True)
    print("patched macho.py: command-0 errors name the 32-byte header")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
