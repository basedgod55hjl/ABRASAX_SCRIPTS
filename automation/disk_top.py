"""Top-level disk consumers on C: -- for targeting the next reclaim pass."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

rows = []
for entry in Path("C:/").iterdir():
    try:
        if entry.is_dir():
            total = 0
            for dp, _dn, fns in os.walk(entry):
                for fn in fns:
                    try:
                        total += (Path(dp) / fn).stat().st_size
                    except OSError:
                        pass
            rows.append((total, entry.name + "/"))
        else:
            rows.append((entry.stat().st_size, entry.name))
    except OSError:
        continue

rows.sort(reverse=True)
print(f"C: free {shutil.disk_usage('C:/').free/1e9:.1f} GB\n")
print(f"{'GB':>8}  path")
for b, name in rows[:18]:
    print(f"{b/1e9:8.1f}  {name}")
