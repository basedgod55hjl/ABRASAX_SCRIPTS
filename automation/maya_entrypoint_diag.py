"""Instrument the entrypoint path to see exactly where stdout dies.

Facts so far:
  * python -c print   -> works inherited AND captured
  * entrypoint file-marker test -> child RAN (marker written) but stdout empty
That combination means the child runs and prints, but its output goes nowhere
reachable. Instrument the wrapper to record its own stdout object and the
child's.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PY = sys.executable
ENTRY = Path(r"C:\ABRASAX\TYPESCRIPT\maya\docker\entrypoint.py")
MARK = Path(r"C:\ABRASAX\LOGS\diag_entry.txt")

# A child that records what it thinks its stdout is, then prints.
child = textwrap.dedent(f"""
    import sys, os
    with open(r'{MARK}', 'w') as f:
        f.write('stdout=%r\\n' % (sys.stdout,))
        f.write('fileno=%s\\n' % getattr(sys.stdout, 'fileno', lambda: 'n/a')())
        try:
            f.write('isatty=%s\\n' % sys.stdout.isatty())
        except Exception as e:
            f.write('isatty_err=%s\\n' % e)
    print('CHILD-PRINTED')
    sys.stdout.flush()
""")

if MARK.exists():
    MARK.unlink()

r = subprocess.run([PY, str(ENTRY), PY, "-c", child],
                   capture_output=True, text=True, timeout=180)
print("wrapper rc     :", r.returncode)
print("wrapper stdout :", repr(r.stdout))
print("wrapper stderr :", repr(r.stderr[:300]))
print("child diag file:", MARK.exists())
if MARK.exists():
    print(MARK.read_text())

# control: the same child, no entrypoint
MARK.unlink()
r2 = subprocess.run([PY, "-c", child], capture_output=True, text=True, timeout=180)
print("\ncontrol rc     :", r2.returncode)
print("control stdout :", repr(r2.stdout))
