"""Watch an installer process: CPU delta + install-log growth.

Generalises watch_unity_install.py to any PID/log so both the Unity setup and the
Epic MSI can be diagnosed the same way. Distinguishes progressing / spinning /
wedged, which matters because both installers on this host have shown stalls and
the cause has to be evidence-based.
"""
import os
import subprocess
import sys
import time

pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
log = sys.argv[2] if len(sys.argv) > 2 else None
watch_dir = sys.argv[3] if len(sys.argv) > 3 else None


def cpu(pid):
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"try{{(Get-Process -Id {pid} -ErrorAction Stop).CPU}}catch{{-1}}"],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return -1.0


def loglines(path):
    if not path or not os.path.exists(path):
        return -1
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return n


def tree_bytes(root):
    if not root or not os.path.isdir(root):
        return 0
    t = 0
    for dp, _, fns in os.walk(root):
        for fn in fns:
            try:
                t += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return t


c0 = cpu(pid)
l0 = loglines(log)
d0 = tree_bytes(watch_dir)
print(f"t0  cpu={c0:8.1f}s  loglines={l0:6d}  tree={d0 / 1e6:8.1f} MB")

time.sleep(25)

c1 = cpu(pid)
if c1 < 0:
    print("process exited during the window")
    sys.exit(0)
l1 = loglines(log)
d1 = tree_bytes(watch_dir)
print(f"t1  cpu={c1:8.1f}s  loglines={l1:6d}  tree={d1 / 1e6:8.1f} MB")
print(f"Δ   cpu={c1 - c0:8.1f}s  loglines={l1 - l0:6d}  tree={(d1 - d0) / 1e6:8.1f} MB")

if d1 - d0 > 1e6 or l1 - l0 > 10:
    print("VERDICT: PROGRESSING")
elif c1 - c0 > 1.0:
    print("VERDICT: SPINNING (CPU without output)")
else:
    print("VERDICT: WEDGED (idle)")
sys.exit(0)
