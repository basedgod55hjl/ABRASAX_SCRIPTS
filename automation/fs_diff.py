"""Walk a directory with three independent APIs and diff them.

Written because one PowerShell enumeration returned 145 entries for a folder
whose real content differed. Ground truth needs at least two witnesses.
"""
import os
import sys
from pathlib import Path

target = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\ABRASAX\AGENTS\SKILLS\rust-skills")
print("target:", target)

a = sorted(os.listdir(target))
b = sorted(p.name for p in target.iterdir())
c = sorted(p.name for p in target.glob("*"))
print(f"os.listdir        : {len(a)}")
print(f"Path.iterdir      : {len(b)}")
print(f"Path.glob('*')    : {len(c)}")
print("listdir == iterdir:", a == b, " listdir == glob:", a == c)
if a != b:
    print("only listdir:", sorted(set(a) - set(b)))
    print("only iterdir:", sorted(set(b) - set(a)))

dirs = [n for n in a if (target / n).is_dir()]
print(f"directories: {len(dirs)}  files: {len(a) - len(dirs)}")
for probe in ("imgui", "part", "ui-ux-pro-max", "k-calibration-optimizer"):
    hits = [n for n in a if probe in n.lower()]
    print(f"  contains {probe!r}: {len(hits)} -> {hits[:6]}")

# byte-exact total for the tree
total = 0
files = 0
for dirpath, dirnames, filenames in os.walk(target):
    dirnames[:] = [d for d in dirnames if d not in {"node_modules", ".git"}]
    for fn in filenames:
        try:
            total += (Path(dirpath) / fn).stat().st_size
            files += 1
        except OSError:
            pass
print(f"os.walk files={files} bytes={total}")
