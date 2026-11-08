"""Identify the interpreter the test actually uses and how it handles -c.

maya_gate ran the suite with C:\\ABRASAX\\PYTHON\\.venv_gui\\Scripts\\python.exe,
but a venv 'python.exe' can be a shim that re-execs a base interpreter. If
sys.executable inside that process points somewhere with different argv
handling, the entrypoint would forward args to a different program than the one
that produced the expected output.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

print("sys.executable       :", sys.executable)
print("sys.prefix           :", sys.prefix)
print("sys.base_prefix      :", sys.base_prefix)
print("venv?                :", sys.prefix != sys.base_prefix)

PY = sys.executable
ENTRY = Path(r"C:\ABRASAX\TYPESCRIPT\maya\docker\entrypoint.py")

# 1. does the entrypoint forward at all? ask the child to write to a FILE.
marker = Path(r"C:\ABRASAX\LOGS\maya_child_marker.txt")
if marker.exists():
    marker.unlink()
child = f"open(r'{marker}','w').write('CHILD-RAN')"
r = subprocess.run([PY, str(ENTRY), PY, "-c", child],
                   capture_output=True, text=True, timeout=120)
print("\n[file-marker test] rc:", r.returncode,
      "stdout:", repr(r.stdout[:100]), "stderr:", repr(r.stderr[:200]))
print("  child actually ran:", marker.exists(),
      marker.read_text() if marker.exists() else "")

# 2. same, but capture=False (inherit) to a real file
log = Path(r"C:\ABRASAX\LOGS\maya_inherit.txt")
with log.open("w") as fh:
    r2 = subprocess.run([PY, str(ENTRY), PY, "-c", "print('INHERITED-OUT')"],
                        stdout=fh, stderr=subprocess.STDOUT, timeout=120)
print("[inherit test]      rc:", r2.returncode, "file:", repr(log.read_text()))

# 3. bypass the entrypoint: is forwarding of `-c` itself the problem?
r3 = subprocess.run([PY, "-c", "print('DIRECT-OK')"], capture_output=True, text=True)
print("[direct control]    rc:", r3.returncode, "stdout:", repr(r3.stdout))

# 4. run the entrypoint OUT of process and show what it prints to a real pipe
r4 = subprocess.run([PY, str(ENTRY), PY, "-c", "import sys;print('PIPE-OK');sys.stdout.flush()"],
                    capture_output=True, text=True, timeout=120)
print("[flush test]        rc:", r4.returncode, "stdout:", repr(r4.stdout))
