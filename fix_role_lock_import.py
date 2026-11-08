#!/usr/bin/env python3
"""fix_role_lock_import.py -- the skip path called pytest in a module that never imported it.

`tests/test_import_side_effect_singletons.py` imports ctypes/json/os/subprocess/sys/time, not
pytest: it never needed to. The neighbour-skip path added for the role-lock test uses
pytest.skip/fail, so the first time a live foreign holder was actually present the branch ran
and raised

    NameError: name 'pytest' is not defined

which is a failure, not a skip -- the exact opposite of the intent. Adding the import is the
whole fix; the branch has now been exercised (orchestrator.py held the lock) and passes.

Run: python SCRIPTS/fix_role_lock_import.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent.parent / "tests" / "test_import_side_effect_singletons.py"

OLD = """import time
from pathlib import Path
"""
NEW = """import time
from pathlib import Path

import pytest
"""


def main() -> int:
    text = TEST.read_text(encoding="utf-8")
    done = "\nimport pytest\n" in text
    if "--check" in sys.argv:
        print(("PASS " if done else "FAIL ") + f"test imports pytest={done}")
        return 0 if done else 1
    if done:
        print("already imported: pytest")
        return 0
    if OLD not in text:
        print("FAIL  import block not found")
        return 1
    bak = TEST.with_suffix(".py.bak-pytestimport")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    TEST.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("added: import pytest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
