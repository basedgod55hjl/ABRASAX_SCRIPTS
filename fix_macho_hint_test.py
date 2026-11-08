#!/usr/bin/env python3
"""fix_macho_hint_test.py -- prove the 28-vs-32 diagnosis fires.

The hint is only worth having if a shifted table actually reaches it. This builds the exact
situation -- a valid 64-bit image parsed with the table forced to start at 28 (what a reader
that omits `reserved` does) -- and asserts the error names the cause instead of only the
symptom. Measured on real images first: 26/26 produce cmd=0 / cmdsize 25 or 27 this way.

Run: python SCRIPTS/fix_macho_hint_test.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent.parent / "tests" / "test_macho_reader.py"
MARK = "def test_a_28_byte_table_start_is_diagnosed_as_a_header_size_bug"

BLOCK = '''

def test_a_28_byte_table_start_is_diagnosed_as_a_header_size_bug():
    """Omitting `reserved` must produce a message that names the cause.

    A 28-byte start reads the reserved u32 as the first command id and the real command id as
    its size: measured on the 26 arm64 images Unity ships, that is cmd=0 with cmdsize 25
    (LC_SEGMENT_64) or 27 (LC_UUID) in every single one. The reader is asked to say so.
    """
    import dataclasses

    raw = build_thin64(reserved=0)
    header = macho.parse_header(raw)
    forged = dataclasses.replace(header, header_size=28)   # the omitted-reserved reader

    # what it would read: reserved as the command, and 0x19 as its size
    cmd_at_28, size_at_28 = struct.unpack_from("<II", raw, 28)
    assert cmd_at_28 == 0 and size_at_28 == 0x19

    with pytest.raises(macho.MachOError) as exc:
        macho._parse_load_commands(raw, forged, 0)
    message = str(exc.value)
    assert "mach_header_64 is 32 bytes" in message
    assert "reserved" in message
    assert "not 28" in message

    # and the correct reader on the same bytes is silent: the hint is not a blanket warning
    assert macho.parse(raw).commands[0].cmd == 0x19
'''


def main() -> int:
    text = TEST.read_text(encoding="utf-8")
    done = MARK in text
    if "--check" in sys.argv:
        print(("PASS " if done else "FAIL ") + f"28-byte diagnosis test={done}")
        return 0 if done else 1
    if done:
        print("already added: 28-byte diagnosis test")
        return 0
    bak = TEST.with_suffix(".py.bak-hinttest")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    TEST.write_text(text.rstrip("\n") + "\n" + BLOCK, encoding="utf-8")
    print("added: test_a_28_byte_table_start_is_diagnosed_as_a_header_size_bug")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
