"""Test the pollution hypothesis directly: brain3d after brain.

MEASURED
    tests 67..73        test_brain.py        (incl. brain service probes, CUDA backend)
    test 74 onward      test_brain3d.py      <- the F appears here
    each file ISOLATED  rc=0, no failures

So test_brain3d passes alone and fails after test_brain. The cheapest decisive test
is to run exactly those two files, in that order, and read the failure.

Candidates for the pollution:
  * test_brain leaves a CUDA context or torch device state that brain3d's GL context
    then fights with
  * test_brain starts or stops a brain service, so load_field() in brain3d gets a
    different field than it expects
  * test_brain monkeypatches a module-level name that brain3d imported

The traceback will say which.
"""
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000

print("=== brain + brain3d together, verbose ===")
r = subprocess.run(
    [PY, "-m", "pytest", "TESTS/python/test_brain.py", "TESTS/python/test_brain3d.py",
     "-v", "-p", "no:cacheprovider", "--tb=short"],
    cwd=ROOT, capture_output=True, text=True, errors="replace",
    timeout=400, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)

out = (r.stdout or "") + (r.stderr or "")
lines = out.strip().splitlines()

print(f"  exit code: {r.returncode}")
print("\n  --- lines mentioning FAIL/ERROR ---")
for ln in lines:
    if "FAIL" in ln or "ERROR" in ln or "assert" in ln.lower():
        print(f"    {ln[:160]}")

print("\n  --- last 30 lines ---")
for ln in lines[-30:]:
    print(f"    {ln[:160]}")
