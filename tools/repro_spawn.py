"""Reproduce the exact subprocess call test_brain makes, and time it."""
import subprocess
import sys
import time

SHIM = r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe"
CODE = ("import json;from abrasax import brain as b;s=b.status();"
        "print(json.dumps({k: s[k] for k in ('steps',) if k in s}))")

print("cwd:", r"C:\ABRASAX")
for label, exe in (("shim", SHIM),
                   ("this-interpreter", sys.executable)):
    t = time.time()
    try:
        r = subprocess.run([exe, "-c", CODE], capture_output=True, text=True,
                           timeout=25, cwd=r"C:\ABRASAX")
        print(f"{label}: rc={r.returncode} {time.time()-t:.1f}s "
              f"out={r.stdout.strip()[:80]!r} err={r.stderr.strip()[:100]!r}")
    except subprocess.TimeoutExpired:
        print(f"{label}: TIMEOUT after 25s  <-- deadlock")
