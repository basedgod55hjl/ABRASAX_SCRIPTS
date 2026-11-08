#!/usr/bin/env python3
"""fix_macho_table_sum_test.py -- prove the sizeofcmds equality is enforced.

Two assertions:
  * a table that ends short of sizeofcmds is refused (this is what a shifted or padded table
    looks like structurally, and what ncmds/sizeofcmds disagreement looks like);
  * the correct images still parse -- checked against the real corpus separately.

Run: python SCRIPTS/fix_macho_table_sum_test.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent.parent / "tests" / "test_macho_reader.py"
MARK = "def test_a_table_that_does_not_add_up_to_sizeofcmds_is_refused"

BLOCK = '''

def test_a_table_that_does_not_add_up_to_sizeofcmds_is_refused():
    """ncmds and sizeofcmds must agree with the bytes actually there.

    sizeofcmds is the total size of the load commands by definition. If the walk lands short
    (a shifted table, padding, or an ncmds that undercounts), the reader says so instead of
    silently dropping commands that the header promised.
    """
    seg = segment64("__TEXT")
    body = seg + b"\\x00" * 16                      # 16 bytes no command claims
    raw = header64(1, len(seg) + 16) + body         # sizeofcmds counts them anyway

    with pytest.raises(macho.MachOError) as exc:
        macho.parse(raw)
    message = str(exc.value)
    assert "sizeofcmds" in message
    assert "shifted" in message

    # the same file with an honest sizeofcmds is fine
    honest = header64(1, len(seg)) + seg
    assert len(macho.parse(honest).commands) == 1
'''


def main() -> int:
    text = TEST.read_text(encoding="utf-8")
    done = MARK in text
    if "--check" in sys.argv:
        print(("PASS " if done else "FAIL ") + f"sizeofcmds equality test={done}")
        return 0 if done else 1
    if done:
        print("already added: sizeofcmds equality test")
        return 0
    bak = TEST.with_suffix(".py.bak-tablesumtest")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    TEST.write_text(text.rstrip("\n") + "\n" + BLOCK, encoding="utf-8")
    print("added: test_a_table_that_does_not_add_up_to_sizeofcmds_is_refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
