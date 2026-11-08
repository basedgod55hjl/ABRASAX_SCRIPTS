#!/usr/bin/env python3
"""fix_macho_reader.py -- add the Mach-O reader's CLI verb, and fix its two test stitches.

Three corrections, all measured by tests/test_macho_reader.py:

1. `python -m abrasax macho <file>` did not exist: the CLI's argparse `choices` list is the
   authority for what a verb is, so the module was reachable only by import.
2. The Java/fat-arch disambiguation guessed from `cputype` alone. A `.class` file's bytes 4..8
   are minor_version (0) then major_version (45+), which is also a plausible small
   `cputype`, so the guess failed and the reader reported "fat_arch table runs past EOF"
   for a Java class instead of naming it. The signature is now the exact one: minor == 0 and
   45 <= major <= 100.
3. Two test expectations were arithmetic slips (offset 28 holds `reserved` then `cmd`, so
   the second u32 is 0x19, not 1; a UUID of 16x 0xaa renders as aaaaaaaa-aaaa-...).

Run: python SCRIPTS/fix_macho_reader.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "abrasax" / "cli.py"
MOD = ROOT / "abrasax" / "macho.py"
TEST = ROOT / "tests" / "test_macho_reader.py"

EARLY_ANCHOR = '''        if payload[0] == "units":'''
EARLY_NEW = '''        if payload[0] == "macho":
            from . import macho
            return macho.main(payload[1:])
        if payload[0] == "units":'''

PARSER_ANCHOR = '''    p_mesh = sub.add_parser("mesh", help="phone <-> substrate sensor mesh bridge")'''
PARSER_NEW = '''    p_macho = sub.add_parser("macho", help="Mach-O / fat binary reader (32- and 64-bit)")
    p_macho.add_argument("rest", nargs=argparse.REMAINDER)

    p_mesh = sub.add_parser("mesh", help="phone <-> substrate sensor mesh bridge")'''

DISPATCH_ANCHOR = '''    elif args.command == "mesh":
        from . import mesh_bridge
        return mesh_bridge.main(args.rest)'''
DISPATCH_NEW = '''    elif args.command == "macho":
        from . import macho
        return macho.main(args.rest)
    elif args.command == "mesh":
        from . import mesh_bridge
        return mesh_bridge.main(args.rest)'''

JAVA_OLD = '''    if len(data) < 8:
        return False
    cputype = struct.unpack_from(">i", data, 4)[0]
    return cputype not in CPU_TYPES and cputype > 0x1000'''

JAVA_NEW = '''    if len(data) < 8:
        return False
    # A Java class file puts minor_version (0) and major_version (>=45) exactly where a fat
    # header puts cputype/cpusubtype. Anything else must survive the fat_arch bounds check,
    # which is where a wrong guess gets caught; this signature is exact, not a heuristic.
    minor, major = struct.unpack_from(">HH", data, 4)
    return minor == 0 and 45 <= major <= 100'''

TEST_FIXES = [
    (
        '    assert cmdsize_at_28 == 1, "and its \'cmdsize\' is the first command id (LC_SEGMENT_64)"',
        '    assert cmdsize_at_28 == 0x19, "and its \'cmdsize\' is the first command id (LC_SEGMENT_64)"',
    ),
    (
        '    assert image.uuid == "aaaa" * 8 and "-" in image.uuid',
        '    assert image.uuid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"',
    ),
]


def main() -> int:
    cli = CLI.read_text(encoding="utf-8")
    mod = MOD.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")

    have_cli = 'payload[0] == "macho"' in cli and 'args.command == "macho"' in cli
    have_java = "minor == 0 and 45 <= major <= 100" in mod
    have_tests = all(new in test for _old, new in TEST_FIXES)

    if "--check" in sys.argv:
        ok = have_cli and have_java and have_tests
        print(("PASS " if ok else "FAIL ")
              + f"macho cli={have_cli} java_signature={have_java} test_expectations={have_tests}")
        return 0 if ok else 1
    if have_cli and have_java and have_tests:
        print("already patched: macho cli + java signature + test expectations")
        return 0

    if not have_cli:
        for anchor, new, label in (
            (EARLY_ANCHOR, EARLY_NEW, "early dispatch"),
            (PARSER_ANCHOR, PARSER_NEW, "subparser"),
            (DISPATCH_ANCHOR, DISPATCH_NEW, "argparse dispatch"),
        ):
            if anchor not in cli:
                print(f"FAIL  cli anchor missing: {label}")
                return 1
        cli = cli.replace(EARLY_ANCHOR, EARLY_NEW, 1)
        cli = cli.replace(PARSER_ANCHOR, PARSER_NEW, 1)
        cli = cli.replace(DISPATCH_ANCHOR, DISPATCH_NEW, 1)
        bak = CLI.with_suffix(".py.bak-macho")
        if not bak.exists():
            bak.write_text(CLI.read_text(encoding="utf-8-sig"), encoding="utf-8")
        CLI.write_text(cli, encoding="utf-8")
        print("  + cli: macho verb (early dispatch, subparser, argparse dispatch)")

    if not have_java:
        if JAVA_OLD not in mod:
            print("FAIL  macho java heuristic not found")
            return 1
        MOD.write_text(mod.replace(JAVA_OLD, JAVA_NEW, 1), encoding="utf-8")
        print("  + macho: java class signature (minor==0, 45<=major<=100)")

    if not have_tests:
        for old, new in TEST_FIXES:
            if old not in test:
                print(f"FAIL  test line not found: {old.strip()[:60]}")
                return 1
            test = test.replace(old, new, 1)
        TEST.write_text(test, encoding="utf-8")
        print("  + tests: corrected two expectations")

    print("patched macho reader wiring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
