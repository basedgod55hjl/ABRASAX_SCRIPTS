"""Report progress of the $WINDOWS.~BT reclaim without PowerShell quoting issues."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

P = Path("C:/$WINDOWS.~BT")
n = b = 0
for dirpath, _d, filenames in os.walk(P):
    for fn in filenames:
        try:
            st = (Path(dirpath) / fn).stat()
        except OSError:
            continue
        n += 1
        b += st.st_size
print(f"files remaining: {n}   {b/1e9:.2f} GB   exists={P.exists()}")

out = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'takeown|icacls|python' } | "
     "ForEach-Object { \"$($_.ProcessId) $($_.Name)\" }"],
    capture_output=True, text=True, timeout=120)
print("relevant processes:")
for ln in out.stdout.splitlines():
    if ln.strip():
        print("  ", ln.strip())

print("out file bytes:",
      os.path.getsize(r"C:\ABRASAX\LOGS\rbt.out") if os.path.exists(r"C:\ABRASAX\LOGS\rbt.out") else "?")
