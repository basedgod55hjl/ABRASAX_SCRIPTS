#!/usr/bin/env python3
"""fix_role_lock_skip.py -- a lock a live neighbour holds is not measurable, so skip.

After the retry fix, `test_importing_does_not_take_the_role_lock` still failed once in a full
run: pid 20016 (`python orchestrator.py`, started by the Hermes resurrect watchdog) holds
LOGS/locks/orchestrator.lock for its whole life. No number of retries clears that, and it is
not the import's doing -- the test simply cannot observe its subject while a foreign live
process owns the lock.

The honest outcomes are now:
  * import child took the lock        -> FAIL (the defect this test exists to catch)
  * a dead pid is left behind         -> FAIL (a leak: the lock must be released on exit)
  * a live foreign process holds it   -> SKIP, naming the pid, because the measurement is
                                        impossible rather than the code being wrong

Run: python SCRIPTS/fix_role_lock_skip.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

TEST = Path(__file__).resolve().parent.parent / "tests" / "test_import_side_effect_singletons.py"

OLD = '''        assert foreign is None, (
            f"the {role} lock was still held (pid {foreign}) after 3 clean imports of "
            f"{module} -- a neighbour keeps taking it, or the import leaks it")'''

NEW = '''        if foreign is not None:
            if not _pid_alive(foreign):
                pytest.fail(
                    f"importing {module} left a dead pid {foreign} in the {role} lock: the "
                    f"lock must be released when the import returns")
            pytest.skip(
                f"a live neighbour (pid {foreign}) owns the {role} lock, so the import's own "
                f"behaviour cannot be measured -- not a defect in {module}")'''

MARK = "cannot be measured"


def main() -> int:
    text = TEST.read_text(encoding="utf-8")
    if "--check" in sys.argv:
        done = MARK in text
        print(("PASS " if done else "FAIL ") + f"role-lock neighbour skip={done}")
        return 0 if done else 1
    if MARK in text:
        print("already patched: role-lock neighbour skip")
        return 0
    if OLD not in text:
        print("FAIL  assertion tail not found (file changed?)")
        return 1
    bak = TEST.with_suffix(".py.bak-lockskip")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    TEST.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: a live foreign holder now skips instead of failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
