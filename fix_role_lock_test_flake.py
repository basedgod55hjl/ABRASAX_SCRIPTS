#!/usr/bin/env python3
"""fix_role_lock_test_flake.py -- the lock test must measure the import, not the neighbours.

`test_importing_does_not_take_the_role_lock` clears a stale lock, imports the module in a
child, and asserts no lock is held afterwards. That assertion is only about the child. On a
live box other spawners (the supervisor and C:\\vlc-build\\resurrect_watchdog.py's host role)
claim the same lock whenever they feel like it, so the test fails intermittently for a reason
that has nothing to do with import side effects -- measured 2026-11-02: 503/503 passed twice,
then one run failed while a neighbouring process held the lock.

The measurement now repeats up to three times and only fails when the lock is still held
*after a clean import* in every attempt, or when the holder is the import child itself (the
real defect this test exists to catch).

Run: python SCRIPTS/fix_role_lock_test_flake.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent.parent / "tests" / "test_import_side_effect_singletons.py"

OLD = '''def test_importing_does_not_take_the_role_lock():
    for module, role in TARGETS.items():
        _clear_if_stale(role)
        rc, out, pid = _import_in_child(module[:-3])
        assert rc == 0, f"import {module} exited {rc}: {out[-600:]}"
        assert "IMPORTED" in out, f"import {module} died silently: {out[-600:]!r}"
        holder = _lock_pid(role)
        assert holder == 0, f"importing {module} claimed the {role} lock (pid {holder})"
        assert holder != pid
'''

NEW = '''def test_importing_does_not_take_the_role_lock():
    """The child must not claim the role lock.

    A holder that appears during the window may be a neighbouring spawner (supervisor,
    resurrect_watchdog), which is not this test's subject. Only the child holding the lock
    is a defect; a foreign live holder re-runs the measurement instead of failing it.
    """
    for module, role in TARGETS.items():
        foreign = None
        for attempt in range(3):
            _clear_if_stale(role)
            rc, out, pid = _import_in_child(module[:-3])
            assert rc == 0, f"import {module} exited {rc}: {out[-600:]}"
            assert "IMPORTED" in out, f"import {module} died silently: {out[-600:]!r}"
            holder = _lock_pid(role)
            assert holder != pid, f"importing {module} claimed the {role} lock (pid {holder})"
            if holder == 0:
                foreign = None
                break
            foreign = holder
        assert foreign is None, (
            f"the {role} lock was still held (pid {foreign}) after 3 clean imports of "
            f"{module} -- a neighbour keeps taking it, or the import leaks it")
'''

MARK = "a neighbour keeps taking it"


def main() -> int:
    text = TEST.read_text(encoding="utf-8")
    applied = MARK in text
    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"role-lock test hardened={applied}")
        return 0 if applied else 1
    if applied:
        print("already patched: role-lock test")
        return 0
    if OLD not in text:
        print("FAIL  test body not found (file changed?)")
        return 1
    bak = TEST.with_suffix(".py.bak-lockflake")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    TEST.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: role-lock test ignores foreign holders, fails on the import child")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
