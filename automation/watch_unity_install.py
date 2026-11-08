"""Watch the Unity installer: is it actually progressing?

Reports CPU delta and disk growth over a sampling window. Distinguishes
"working hard" from "spinning" from "wedged" -- the three states this installer
has plausibly been in since launch.
"""
import os
import subprocess
import sys
import time

PROC = "UnitySetup64-6000.6.6f1"
ROOT = r"C:\Program Files\Unity"


def cpu_seconds():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"try{{(Get-Process {PROC} -ErrorAction Stop).CPU}}catch{{-1}}"],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return -1.0


def dir_bytes():
    total = 0
    for dp, _, fns in os.walk(ROOT):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return total


c0, d0 = cpu_seconds(), dir_bytes()
if c0 < 0:
    print("installer not running")
    sys.exit(0)

print(f"start  cpu={c0:8.1f}s  disk={d0 / 1e6:9.1f} MB")
time.sleep(25)
c1, d1 = cpu_seconds(), dir_bytes()
if c1 < 0:
    print("installer exited during the window")
    sys.exit(0)
print(f"end    cpu={c1:8.1f}s  disk={d1 / 1e6:9.1f} MB")
print(f"delta  cpu={c1 - c0:8.1f}s  disk={(d1 - d0) / 1e6:9.1f} MB")

if d1 - d0 > 1e6:
    print("VERDICT: PROGRESSING (writing files)")
elif c1 - c0 > 1.0:
    print("VERDICT: SPINNING (burning CPU, writing nothing)")
else:
    print("VERDICT: WEDGED (no CPU, no disk)")
sys.exit(0)
