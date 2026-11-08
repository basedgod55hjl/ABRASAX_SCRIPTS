"""Read a process's real I/O counters (Windows), not just CPU.

CPU alone cannot distinguish "spinning in a retry loop" from "decompressing".
ReadTransferCount counts every byte the process has read through its I/O manager
handles, so if the installer is making progress on a 3.86 GB payload the read
counter must climb; if it is spinning on an error, read stalls while CPU climbs.
"""
import subprocess
import sys
import time

PROC = sys.argv[1] if len(sys.argv) > 1 else "UnitySetup64-6000.6.6f1"


def sample():
    ps = (
        "$p=Get-Process %s -ErrorAction SilentlyContinue;"
        "if($p){ \"{0}|{1}|{2}|{3}\" -f $p.CPU,$p.WorkingSet64,"
        "((Get-CimInstance Win32_Process -Filter \"ProcessId=$($p.Id)\").ReadTransferCount),"
        "((Get-CimInstance Win32_Process -Filter \"ProcessId=$($p.Id)\").WriteTransferCount) }"
        % PROC
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True)
    t = out.stdout.strip()
    if "|" not in t:
        return None
    c, ws, rd, wr = t.split("|")
    return float(c), int(ws), int(rd), int(wr)


a = sample()
if a is None:
    print(f"{PROC} not running")
    sys.exit(0)
print(f"t0 cpu={a[0]:8.1f}s ws={a[1] / 1e6:7.1f}MB read={a[2] / 1e6:10.1f}MB write={a[3] / 1e6:10.1f}MB")

time.sleep(25)

b = sample()
if b is None:
    print("process exited")
    sys.exit(0)
print(f"t1 cpu={b[0]:8.1f}s ws={b[1] / 1e6:7.1f}MB read={b[2] / 1e6:10.1f}MB write={b[3] / 1e6:10.1f}MB")
print(f"Δ  cpu={b[0] - a[0]:8.1f}s ws={(b[1] - a[1]) / 1e6:+7.1f}MB "
      f"read={(b[2] - a[2]) / 1e6:+10.1f}MB write={(b[3] - a[3]) / 1e6:+10.1f}MB")

if b[3] - a[3] > 1e6:
    print("VERDICT: WRITING (real progress)")
elif b[2] - a[2] > 1e6:
    print("VERDICT: READING (decompressing payload)")
elif b[0] - a[0] > 1.0:
    print("VERDICT: SPINNING (CPU only, no I/O)")
else:
    print("VERDICT: WEDGED (idle, no I/O)")
sys.exit(0)
