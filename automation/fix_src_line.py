"""Repair the SRC line in verify_unity_runtime_contract.py, exactly.

PowerShell quote-escaping mangled it twice:
    SRC = str(paths.unity_scripts / "FloatingBrainRenderer.cs)     <- missing quote
    SRC = str(paths.unity_scripts / FloatingBrainRenderer.cs)      <- quotes gone

The second form COMPILES (py_compile exit 0) because it parses as attribute access
on a module-level name, and would fail at runtime with NameError. That is a worse
outcome than a syntax error, and it is why this is done in Python, where the exact
bytes are controlled.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_unity_runtime_contract.py"
src = open(PATH, encoding="utf-8").read()

GOOD = 'SRC = str(paths.unity_scripts / "FloatingBrainRenderer.cs")'

# replace whatever the SRC assignment currently is
pattern = re.compile(r'^SRC\s*=\s*.*$', re.M)
matches = pattern.findall(src)
if not matches:
    print("ANCHOR-NOT-FOUND: no SRC assignment")
    sys.exit(1)

src = pattern.sub(GOOD, src, count=1)
open(PATH, "w", encoding="utf-8", newline="").write(src)

# verify byte-exactly
check = open(PATH, encoding="utf-8").read()
line = [ln for ln in check.splitlines() if ln.startswith("SRC =")]
print("SRC line now:", line[0] if line else "MISSING")
print("exact match :", line and line[0].strip() == GOOD)

# and it must actually run
import subprocess
r = subprocess.run([r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe",
                    "-u", PATH],
                   capture_output=True, text=True, timeout=180)
print("\nexit:", r.returncode)
tail = (r.stdout or "").strip().splitlines()[-4:]
for ln in tail:
    print("  " + ln)
if r.stderr.strip():
    print("  stderr:", r.stderr.strip().splitlines()[-1][:120])
sys.exit(0 if r.returncode == 0 else 1)
