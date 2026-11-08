"""Is the name consistent? Scope to the live package, which is what matters."""
import collections
import pathlib
import re
import sys

sys.path.insert(0, r"C:\ABRASAX")

ROOT = pathlib.Path(r"C:\ABRASAX")

print("=== abrasax/ package ===")
c = collections.Counter()
hits = []
for f in (ROOT / "abrasax").rglob("*.py"):
    try:
        t = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    c["ABRASAX"] += len(re.findall(r"ABRASAX", t))
    c["ABRAXIS"] += len(re.findall(r"ABRAXIS", t))
    for i, line in enumerate(t.splitlines(), 1):
        if re.search(r"\bABRAXIS\b", line):
            hits.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:80]}")
for k, v in c.most_common():
    print(f"  {k:<10} {v}")
print(f"  remaining ABRAXIS lines: {hits or 'none'}")

print("\n=== SCRIPTS/ (my own tooling) ===")
c2 = collections.Counter()
h2 = []
for f in (ROOT / "SCRIPTS").rglob("*.py"):
    try:
        t = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    if "probe_name" in f.name or "_check_name" in f.name:
        continue
    c2["ABRASAX"] += len(re.findall(r"ABRASAX", t))
    c2["ABRAXIS"] += len(re.findall(r"ABRAXIS", t))
    for i, line in enumerate(t.splitlines(), 1):
        if re.search(r"\bABRAXIS\b", line):
            h2.append(f"{f.name}:{i}: {line.strip()[:70]}")
for k, v in c2.most_common():
    print(f"  {k:<10} {v}")
print(f"  ABRAXIS lines: {h2 or 'none'}")

print("\n=== what a user sees ===")
page = (ROOT / "abrasax" / "nervous_ui.py").read_text(encoding="utf-8")
for m in re.finditer(r"<title>([^<]+)</title>|<h1>([^<]+)</h1>", page):
    print("  ", m.group(1) or m.group(2))
cli = (ROOT / "abrasax" / "cli.py").read_text(encoding="utf-8")
for line in cli.splitlines():
    if 'description="ABRASAX' in line:
        print("  cli:", line.strip()[:70])
