"""Measure C:\\$WINDOWS.~BT (the Windows Setup upgrade sandbox).

PowerShell's $ interpolation makes this path awkward; Python has no such issue,
so it does the enumeration. Read-only: this script never deletes.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

P = Path("C:/$WINDOWS.~BT")

if not P.exists():
    print("MISSING", P)
    sys.exit(1)

total = 0
files = 0
newest = (0, None)
per_dir: dict[str, list[int]] = {}

for dirpath, dirnames, filenames in os.walk(P):
    for fn in filenames:
        fp = Path(dirpath) / fn
        try:
            st = fp.stat()
        except OSError:
            continue
        files += 1
        total += st.st_size
        rel = Path(dirpath).relative_to(P)
        key = rel.parts[0] if rel.parts else "(root)"
        d = per_dir.setdefault(key, [0, 0])
        d[0] += 1
        d[1] += st.st_size
        if st.st_mtime > newest[0]:
            newest = (st.st_mtime, str(fp))

print(f"files: {files}   size: {total/1e6:.1f} MB")
print("\nper top-level directory:")
for name, (n, b) in sorted(per_dir.items(), key=lambda kv: -kv[1][1]):
    print(f"  {name:24} {n:6} files {b/1e6:9.1f} MB")
if newest[1]:
    print(f"\nnewest: {time.strftime('%Y-%m-%d %H:%M', time.localtime(newest[0]))}  {newest[1]}")

# What marks this as an in-flight vs abandoned upgrade?
print("\nkey markers:")
for probe in ("Sources/setup.exe", "Sources/setupcore.dll", "Sources/Panther",
              "Sources/SetupPlatform.exe", "Efi/Microsoft/boot", "Sources/install.wim"):
    q = P / probe
    print(f"  {'yes' if q.exists() else 'no ':3} {probe}")
