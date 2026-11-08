"""Fix meta_check_audit.py: the live-pid probe used an already-dead pid.

The check did:
    mypid = powershell -Command "$PID"     # -> that child's pid
then asked whether that pid is alive. By the time the query ran, that child had
exited, so "no" was the CORRECT answer and the check itself was broken.

Pick a pid that is guaranteed alive at query time: a long-lived process observed
from the process table itself (this python process). The audit's own run_ps runs
a fresh child, so we pass in a pid we know persists.
"""
import os
import subprocess
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\meta_check_audit.py"
src = open(PATH, encoding="utf-8").read()

if "os.getpid()" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''# and a real pid as alive
import subprocess
mypid = subprocess.run(
    ["powershell", "-NoProfile", "-Command", "$PID"],
    capture_output=True, text=True).stdout.strip()
alive2 = audit.run_ps(f"if (Get-Process -Id {mypid} -EA 0) {{'yes'}} else {{'no'}}")
report("a live pid is detected as alive", alive2.strip() == "yes", f"got {alive2!r}")'''

NEW = '''# and a real pid as alive.
# Use THIS process: it is guaranteed to exist while the check runs. Asking a
# child PowerShell for its own $PID gives a pid that dies the moment that child
# exits, which made the previous version of this check report a false failure.
mypid = os.getpid()
alive2 = audit.run_ps(f"if (Get-Process -Id {mypid} -EA 0) {{'yes'}} else {{'no'}}")
report("a live pid is detected as alive", alive2.strip() == "yes",
       f"pid {mypid} -> {alive2!r}")'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: live-pid block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: live-pid probe now uses this process's own pid")
