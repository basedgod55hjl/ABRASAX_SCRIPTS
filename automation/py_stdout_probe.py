"""Test whether the interpreter ITSELF fails to write under inherited stdout.

If `python -c "print(...)" > file` yields an empty file, the problem is the
interpreter/console wiring, not maya's entrypoint at all.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PY = sys.executable
LOGS = Path(r"C:\ABRASAX\LOGS")

print("PY:", PY)
# 1. inherited stdout to a real file
f1 = LOGS / "pyinherit.txt"
with f1.open("w", encoding="utf-8") as fh:
    r = subprocess.run([PY, "-c", "print('INHERIT_DIRECT')"], stdout=fh,
                       stderr=subprocess.STDOUT)
print("1 inherited-to-file   rc=", r.returncode, "content=", repr(f1.read_text()))
print("  os.path.exists:", f1.exists(), "size:", f1.stat().st_size)

# 2. captured (pipe)
r2 = subprocess.run([PY, "-c", "print('CAPTURED_DIRECT')"], capture_output=True, text=True)
print("2 captured            rc=", r2.returncode, "stdout=", repr(r2.stdout))

# 3. os.system style (windows console)
rc = os.system(f'"{PY}" -c "print(\'OSSYSTEM\')" > "{LOGS / "osys.txt"}"')
print("3 os.system rc=", rc, "content=", repr((LOGS / "osys.txt").read_text(errors="replace")))

# 4. does python -u change it?
f4 = LOGS / "pyinherit_u.txt"
with f4.open("w", encoding="utf-8") as fh:
    r4 = subprocess.run([PY, "-u", "-c", "print('UNBUFFERED')"], stdout=fh,
                        stderr=subprocess.STDOUT)
print("4 -u inherited        rc=", r4.returncode, "content=", repr(f4.read_text()))
