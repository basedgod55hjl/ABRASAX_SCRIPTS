"""Which test is the F at position 74, and why does the suite stall after it?

The full run printed:
    .........F.............................................. [ 64%]
then never advanced for 25 minutes and had to be killed.

Two separate problems:
  1  one test FAILED (the F)
  2  the run HUNG -- a later test or a teardown blocked

pytest -x with -v names the failure immediately, and a per-file run with a timeout
finds the hang. This runs each test FILE separately with a hard timeout so a single
hanging file is identified instead of blocking the whole sweep.
"""
import glob
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
TESTS = os.path.join(ROOT, "TESTS", "python")
CREATE_NO_WINDOW = 0x08000000

files = sorted(glob.glob(os.path.join(TESTS, "test_*.py")))
print(f"running {len(files)} file(s) individually, 120 s budget each\n")

failures = []
hangs = []

for f in files:
    name = os.path.basename(f)
    try:
        r = subprocess.run([PY, "-m", "pytest", f, "-q", "-p", "no:cacheprovider",
                            "--timeout=100" if False else "-q"],
                           cwd=ROOT, capture_output=True, text=True, errors="replace",
                           timeout=120, stdin=subprocess.DEVNULL,
                           creationflags=CREATE_NO_WINDOW)
        out = (r.stdout or "") + (r.stderr or "")
        last = [ln for ln in out.strip().splitlines() if ln.strip()]
        summary = last[-1] if last else "(no output)"
        status = "ok  " if r.returncode == 0 else "FAIL"
        if r.returncode != 0:
            failures.append((name, summary))
        print(f"  {status} {name:34s} rc={r.returncode}  {summary[:70]}")
    except subprocess.TimeoutExpired:
        hangs.append(name)
        print(f"  HANG {name:34s} exceeded 120 s -- killed")

print("\n=== FAILURES ===")
for n, s in failures:
    print(f"  {n}\n      {s}")
if not failures:
    print("  none")

print("\n=== HANGS ===")
for n in hangs:
    print(f"  {n}")
if not hangs:
    print("  none")
