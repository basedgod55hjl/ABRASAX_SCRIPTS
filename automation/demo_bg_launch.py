"""End-to-end proof: restart the scene verifier in the background using winproc.

This is the real use case the directive was about. Previously a background job was
started in the tool shell as:

    start /b "" cmd /c "python x.py > log 2>&1" & timeout /t 30 >nul

and `timeout /t` produced

    ERROR: Input redirection is not supported, exiting the process immediately.

so the launch appeared to fail. This does the same job with winproc, polls for the
result, and prints the captured output.
"""
import os
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

import winproc  # noqa: E402

LOGS = r"C:\ABRASAX\LOGS"
PY = r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe"
SCRIPT = r"C:\ABRASAX\SCRIPTS\automation\check_abra_paths.py"
OUT = os.path.join(LOGS, "_bg_paths.log")

if os.path.exists(OUT):
    os.remove(OUT)

print(f"launching {os.path.basename(SCRIPT)} in the background ...")
p = winproc.launch([PY, "-u", SCRIPT], stdout_path=OUT)
print(f"  pid {p.pid}")

appeared = winproc.wait_for_file(OUT, timeout=60)
print(f"  output file appeared: {appeared}")

exited, rc = winproc.wait_for_exit(p, timeout=120)
print(f"  exited: {exited}  returncode: {rc}")

tail = winproc.read_tail(OUT, 5)
print("\n--- captured output ---")
print(tail)

ok = exited and rc == 0 and "PASS" in tail
print("\nRESULT:", "PASS -- background job ran, polled and captured without a console"
      if ok else "FAIL")
sys.exit(0 if ok else 1)
