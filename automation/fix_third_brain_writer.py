#!/usr/bin/env python3
"""fix_third_brain_writer.py -- neutralize tools/brain_state.py as a writer.

Third writer found 2026-10-31: tools/selftest_all.py line 184 ran
`tools/brain_state.py`, whose main() rewrote LOGS/brain_state.json with a
DISTINCT schema -- no heartbeat, no embed_mode/embed_dim/embed_ok, spine as a
LIST (the canonical writer emits spine as a SCALAR plus spine_points). Because
the self-test ran it every suite, the overlay's input lost the freshness and
embed fields and test_overlay_jev_wiring failed again with age=24.4s.

Three writers now identified, all targeting C:\\abrasax\\LOGS\\brain_state.json:
  * tools/brain_state_writer.py        canonical (atomic, embed_ok, heartbeat)
  * ENGINE/floating_brain/jev_brain_state.py  retired, unsupervisied by
                                        fix_dual_brain_writer.py
  * tools/brain_state.py               this one

This makes `tools/brain_state.py <anything> --check-only` (the new self-test
call) a pure READER that never writes, and leaves its geometry checks intact.
Idempotent.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TREE = Path(r"C:\abrasax")
BS = TREE / "tools" / "brain_state.py"
SELF = TREE / "tools" / "selftest_all.py"

OLD_MAIN = 'def main():\n    os.makedirs(LOGS, exist_ok=True)'
NEW_MAIN = '''def main():
    # NEVER write LOGS/brain_state.json from here: tools/brain_state_writer.py
    # is the ONE writer. This script emits a different schema (list spine, no
    # heartbeat/embed_*), and when selftest_all ran it the overlay's input lost
    # those fields and went stale. --check-only prints and returns instead.
    check_only = "--check-only" in sys.argv
    os.makedirs(LOGS, exist_ok=True)'''


def main() -> int:
    src = BS.read_text(encoding="utf-8")
    if "check_only" in src:
        print("brain_state.py already guarded")
    else:
        if OLD_MAIN not in src:
            print("FAIL: main() header not found in tools/brain_state.py")
            return 2
        bak = BS.with_suffix(".py.bak-3rdwriter")
        if not bak.exists():
            bak.write_text(src, encoding="utf-8")
            print("backup ->", bak)
        src = src.replace(OLD_MAIN, NEW_MAIN, 1)
        # insert the early return right before the atomic write block
        write_block = ('    out = os.path.join(LOGS, "brain_state.json")')
        if write_block not in src:
            print("FAIL: write block not found")
            return 3
        src = src.replace(
            write_block,
            '    if check_only:\n'
            '        print(json.dumps({k: v for k, v in state.items() if k != "spine"},\n'
            '                         indent=2))\n'
            '        print("check-only: brain_state.json NOT written "\n'
            '              "(tools/brain_state_writer.py is the ONE writer)")\n'
            '        return 0\n'
            + write_block,
            1,
        )
        BS.write_text(src, encoding="utf-8")
        print("guarded tools/brain_state.py")

    rc = subprocess.run([sys.executable, "-m", "py_compile", str(BS)],
                        capture_output=True, text=True)
    print("py_compile rc=%d %s" % (rc.returncode, rc.stderr.strip()[:300]))
    if rc.returncode:
        return 4

    # point the self-test at the read-only mode
    s = SELF.read_text(encoding="utf-8")
    old = 'run("brain_state geometry", [os.path.join(TOOLS, "brain_state.py")])'
    new = ('run("brain_state geometry",\n'
           '        [os.path.join(TOOLS, "brain_state.py"), "--check-only"])')
    if new in s:
        print("selftest_all.py already uses --check-only")
    elif old in s:
        SELF.write_text(s.replace(old, new, 1), encoding="utf-8")
        print("selftest_all.py -> --check-only")
    else:
        print("FAIL: selftest_all.py call site not found")
        return 5

    rc2 = subprocess.run([sys.executable, "-m", "py_compile", str(SELF)],
                         capture_output=True, text=True)
    print("selftest py_compile rc=%d %s" % (rc2.returncode, rc2.stderr.strip()[:300]))
    return 0 if rc2.returncode == 0 else 6


if __name__ == "__main__":
    sys.exit(main())
