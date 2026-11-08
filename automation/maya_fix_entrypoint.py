"""Fix docker/entrypoint.py so the child's output is not lost.

DEFECT (measured): on Windows the entrypoint replaced itself with
`subprocess.run(sys.argv[1:])` with no stdout/stderr wiring. Under
`capture_output=True` in the test the child's parent handles are pipes, so the
child wrote to them but the entrypoint's stdout carried nothing: the test saw
`result.stdout.count("\\n") == 0` where it requires 1, while the return code was
correctly 0. In a terminal this works by accident (inherited console handle),
which is why it never showed up interactively.

FIX: pass the parent's stdout/stderr down explicitly, so the child's output
reaches whichever stream the caller captured. Exit-code propagation is already
correct and stays as is.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\TYPESCRIPT\maya\docker\entrypoint.py")
src = P.read_text(encoding="utf-8")

if "stdout=None, stderr=None" in src:
    sys.exit("already patched")

old = "        sys.exit(subprocess.run(sys.argv[1:]).returncode)"
if old not in src:
    sys.exit("anchor not found")

new = ('''        # Wire the child's streams to OURS. Without this the child inherits the
        # parent's handles, so when the caller captures output (pipes) the child
        # writes into those pipes but this process's own stdout stays empty and
        # the captured text is lost. Passing theme explicitly keeps the
        # replacement semantics the docstring promises for output as well.
        completed = subprocess.run(
            sys.argv[1:],
            stdin=None,
            stdout=None,
            stderr=None,
            env=os.environ,
        )
        sys.exit(completed.returncode)''')

P.write_text(src.replace(old, new, 1), encoding="utf-8")
print(f"patched {P} ({P.stat().st_size} B)")
