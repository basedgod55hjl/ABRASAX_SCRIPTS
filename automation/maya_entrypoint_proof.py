"""Prove the cause: the entrypoint hands the child a CONSOLE handle, not the pipe.

Diagnosis: with the wrapper the child reports isatty=True and fileno=1, i.e. its
stdout is the console. The control (no wrapper) reports a pipe. So the child's
bytes land on the console and the caller's captured pipe stays empty.

Cause: subprocess.run(..., stdin=None, stdout=None, stderr=None) means
"give the child OUR CURRENT std handles". Those were valid in a console but are
not the redirected pipe a capturing parent expects to see continued. The fix is
to hand the child the parent's ACTUAL stream objects so redirection survives.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PY = sys.executable
ENTRY = Path(r"C:\ABRASAX\TYPESCRIPT\maya\docker\entrypoint.py")
MARK = Path(r"C:\ABRASAX\LOGS\diag2.txt")

child = textwrap.dedent(f"""
    import sys
    with open(r'{MARK}', 'w') as f:
        f.write('isatty=%s\\n' % sys.stdout.isatty())
    print('PAYLOAD')
    sys.stdout.flush()
""")

for label, extra in (("wrapper", [str(ENTRY)]), ("control", [])):
    if MARK.exists():
        MARK.unlink()
    r = subprocess.run([PY, *extra, PY, "-c", child],
                       capture_output=True, text=True, timeout=120)
    diag = MARK.read_text().strip() if MARK.exists() else "(no file)"
    print(f"{label:8} rc={r.returncode} stdout={r.stdout!r} {diag}")
