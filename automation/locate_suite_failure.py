"""The F only appears in the full run. Reproduce it precisely.

MEASURED
    30 test files run INDIVIDUALLY : all rc=0, zero failures, zero hangs
    full run                       : .........F.... at position 74, then stalls

Isolated files pass, so the failure is cross-test state pollution -- one test
leaving something behind that breaks a later one. Two useful facts to pin down:

  1  which TEST is at index 74 in collection order
  2  whether the failure reproduces when the suite is run with -x (stop at first
     failure) and -v (names every test)

This runs the collection with --collect-only first (instant, no execution), prints
the 70th-80th collected ids, then runs -x -v with a timeout so a hang cannot hide it.
"""
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000


def run(args, timeout):
    return subprocess.run([PY, "-m", "pytest"] + args, cwd=ROOT,
                          capture_output=True, text=True, errors="replace",
                          timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=CREATE_NO_WINDOW)


print("=== collection order, items 68..82 ===")
try:
    r = run(["--collect-only", "-q", "-p", "no:cacheprovider"], 180)
    ids = [ln.strip() for ln in (r.stdout or "").splitlines()
           if "::" in ln and ln.strip()]
    print(f"  collected: {len(ids)} test ids")
    for i in range(67, min(82, len(ids))):
        mark = " <<<" if i == 73 else ""
        print(f"  [{i:3d}] {ids[i]}{mark}")
except subprocess.TimeoutExpired:
    print("  collection itself timed out")

print("\n=== run with -x -v, stop at the first failure (300 s budget) ===")
try:
    r = run(["-x", "-v", "-p", "no:cacheprovider"], 300)
    out = (r.stdout or "") + (r.stderr or "")
    lines = out.strip().splitlines()
    fails = [ln for ln in lines if "FAILED" in ln or "ERROR" in ln]
    if fails:
        print("  FIRST FAILURE:")
        for ln in fails[:4]:
            print(f"    {ln.strip()[:150]}")
        # print the traceback body
        idx = next((i for i, ln in enumerate(lines) if "FAILURES" in ln), None)
        if idx is not None:
            print("\n  traceback (first 30 lines):")
            for ln in lines[idx:idx + 30]:
                print(f"    {ln[:150]}")
    else:
        tail = [ln for ln in lines if ln.strip()][-4:]
        print("  no FAILED lines; tail:")
        for ln in tail:
            print(f"    {ln[:150]}")
    print(f"\n  exit code: {r.returncode}")
except subprocess.TimeoutExpired:
    print("  the -x run itself hung past 300 s -- that is the second defect")

print("\n=== interpretation ===")
print("  If a failure is named above, the F is that test when run after its")
print("  predecessors. Compare with the isolated result (all rc=0) to identify what")
print("  it inherits: a mutated module attribute, a leaked temp file, a started")
print("  process, or an environment variable.")
