"""Determine which `timeout /t` forms actually break, and fix only those.

Do not "fix" 24 call sites on a hunch. Measure each form.

Windows timeout.exe has a known failure mode:
    timeout /t 1 >nul
    ERROR: Input redirection is not supported, exiting the process immediately.

The theory to test is that `>nul` (stdout to nul) is fine, but the utility still
needs a console on stdin, and `/nobreak` does not change that. If true, EVERY
`timeout /t` in a .bat fails when the .bat is launched without a console -- which
is exactly how a scheduled task or a background launcher runs it.

This measures, per form, inside a detached process with no console:
    1   timeout /t 1
    2   timeout /t 1 >nul
    3   timeout /t 1 /nobreak >nul
    4   ping -n 2 127.0.0.1 >nul        (the classic portable sleep)
    5   powershell Start-Sleep 1        (portable, no console needed)
    6   Python time.sleep(1)            (what winproc uses)

Exit 0 always -- this is a measurement.
"""
import os
import subprocess
import sys
import time

LOGS = r"C:\ABRASAX\LOGS" + "_timeout_probe"
CREATE_NO_WINDOW = 0x08000000

FORMS = [
    ("timeout /t 1",                 "timeout /t 1"),
    ("timeout /t 1 >nul",            "timeout /t 1 >nul"),
    ("timeout /t 1 /nobreak >nul",   "timeout /t 1 /nobreak >nul"),
    ("ping -n 2 127.0.0.1 >nul",     "ping -n 2 127.0.0.1 >nul"),
    ("powershell Start-Sleep 1",     "powershell -NoProfile -NonInteractive -Command Start-Sleep -Seconds 1"),
]

print(f"{'form':34s} {'rc':>4} {'secs':>6}  stderr")
print("-" * 78)

results = {}
for label, cmd in FORMS:
    t0 = time.time()
    p = subprocess.run(
        ["cmd.exe", "/c", cmd],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    dt = time.time() - t0
    err = (p.stderr or "").strip().splitlines()
    err = err[0][:38] if err else ""
    results[label] = (p.returncode, dt, err)
    print(f"{label:34s} {p.returncode:>4} {dt:>6.2f}  {err}")

# also test the pure-Python form winproc uses
t0 = time.time()
time.sleep(1)
print(f"{'python time.sleep(1)':34s} {0:>4} {time.time() - t0:>6.2f}  (no subprocess)")

print("\n--- verdict ---")
broken = [k for k, (rc, dt, err) in results.items() if k.startswith("timeout")
          and (rc != 0 or "Input redirection" in (err or ""))]
works = [k for k, (rc, dt, err) in results.items()
         if rc == 0 and "Input redirection" not in (err or "")]

print(f"  failing forms : {broken if broken else 'none in this context'}")
print(f"  working forms : {works}")
print("\n  NOTE: whether timeout /t fails depends on the console the caller has.")
print("  A .bat run from a scheduled task or a detached launcher has NO console,")
print("  which is when this bites. The portable sleep (ping or Start-Sleep) is")
print("  safe in both contexts, so launchers should use one of those.")

sys.exit(0)
