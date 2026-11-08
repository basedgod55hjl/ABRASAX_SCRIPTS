#!/usr/bin/env python3
"""fix_macho_field_offsets_test.py -- pin the header field table in the tests.

The operator's statement of the layout is:
    magic(4) cputype(4) cpusubtype(4) filetype(4) ncmds(4) sizeofcmds(4)
i.e. six fields to byte 24, then flags(4) at 24 and reserved(4) at 28, which is exactly why
mach_header_64 is 32 and not 28. Until now the tests pinned the *size*; this pins the
*offsets and signedness*, so a struct that is 32 bytes with the wrong field order, or with an
unsigned cputype, cannot pass.

Measured on UnityPlayer.dylib (131,808,064 B, arm64):
    magic@0=0xfeedfacf  cputype@4=16777228(0x100000C)  cpusubtype@8=0  filetype@12=6
    ncmds@16=43  sizeofcmds@20=6160  flags@24=0x918085  reserved@28=0
    first load command at 32 -> cmd 0x19 (LC_SEGMENT_64)

Run: python SCRIPTS/fix_macho_field_offsets_test.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent.parent / "tests" / "test_macho_reader.py"
MARK = "def test_header_field_offsets_and_signedness_match_the_c_struct"

BLOCK = '''

def test_header_field_offsets_and_signedness_match_the_c_struct():
    """The field table itself, not just the total size.

    magic(4) cputype(4) cpusubtype(4) filetype(4) ncmds(4) sizeofcmds(4) -> 24 bytes,
    then flags(4) at 24 and reserved(4) at 28: 32 in total. cputype/cpusubtype are
    cpu_type_t/cpu_subtype_t (signed); the rest are uint32_t.
    """
    assert macho.MACH_HEADER_64.format == "<IiiIIIII"
    assert macho.MACH_HEADER_32.format == "<IiiIIII"

    expected = [
        ("magic", 0), ("cputype", 4), ("cpusubtype", 8), ("filetype", 12),
        ("ncmds", 16), ("sizeofcmds", 20), ("flags", 24), ("reserved", 28),
    ]
    assert expected[5] == ("sizeofcmds", 20)
    assert expected[5][1] + 4 == 24, "the six named fields end at byte 24"
    assert expected[6] == ("flags", 24)
    assert expected[7] == ("reserved", 28)
    assert expected[7][1] + 4 == macho.MACH_HEADER_64_SIZE == 32

    # the same fields, read by offset, independently of the dataclass
    raw = struct.pack("<IiiIIIII", macho.MH_MAGIC_64, 0x0100000C, 0, 6, 43, 6160, 0x918085, 0)
    assert len(raw) == 32
    assert struct.unpack_from("<I", raw, 0)[0] == macho.MH_MAGIC_64
    assert struct.unpack_from("<i", raw, 4)[0] == 0x0100000C          # cputype, signed
    assert struct.unpack_from("<i", raw, 8)[0] == 0                   # cpusubtype, signed
    assert struct.unpack_from("<I", raw, 12)[0] == 6                  # MH_DYLIB
    assert struct.unpack_from("<I", raw, 16)[0] == 43                 # ncmds
    assert struct.unpack_from("<I", raw, 20)[0] == 6160               # sizeofcmds
    assert struct.unpack_from("<I", raw, 24)[0] == 0x918085           # flags
    assert struct.unpack_from("<I", raw, 28)[0] == 0                  # reserved

    header = macho.parse_header(raw)
    assert (header.cputype, header.filetype, header.ncmds, header.sizeofcmds) == \\
        (0x0100000C, 6, 43, 6160)
    assert header.header_size == 32

    # CPU_TYPE_ANY is -1: a signed cputype must survive as such
    negative = struct.pack("<IiiIIIII", macho.MH_MAGIC_64, -1, 3, 2, 0, 0, 0, 0)
    assert macho.parse_header(negative).cputype == -1
'''


def main() -> int:
    text = TEST.read_text(encoding="utf-8")
    done = MARK in text
    if "--check" in sys.argv:
        print(("PASS " if done else "FAIL ") + f"header field table pinned={done}")
        return 0 if done else 1
    if done:
        print("already pinned: header field offsets")
        return 0
    bak = TEST.with_suffix(".py.bak-offsets")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    TEST.write_text(text.rstrip("\n") + "\n" + BLOCK, encoding="utf-8")
    print("added: test_header_field_offsets_and_signedness_match_the_c_struct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
