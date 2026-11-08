"""The masthead says ABRAXIS WORLD MODEL. Is that the right name?

This tree uses BOTH spellings. Before polishing a title, check which is
authoritative:
    ABRASAX   the root directory, the python package, pyproject name
    ABRAXIS   the masthead, some docs

If they disagree, the masthead is not a design detail - it is the system
calling itself by the wrong name.
"""
import pathlib
import re

ROOT = pathlib.Path(r"C:\ABRASAX")

print("=== where the system names itself in code ===")
for rel in ("pyproject.toml", "abrasax/__init__.py", "abrasax/cli.py"):
    p = ROOT / rel
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(t.splitlines(), 1):
        if re.search(r"ABRA[XS]A[XS]", line, re.I):
            print(f"  {rel}:{i}: {line.strip()[:90]}")

print("\n=== the page ===")
p = ROOT / "abrasax" / "nervous_ui.py"
t = p.read_text(encoding="utf-8", errors="replace")
for i, line in enumerate(t.splitlines(), 1):
    if re.search(r"ABRA[XS]A[XS]", line, re.I):
        print(f"  nervous_ui.py:{i}: {line.strip()[:100]}")

print("\n=== counts across the live tree ===")
import collections
c = collections.Counter()
for f in (ROOT / "abrasax").rglob("*.py"):
    try:
        txt = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    c["ABRASAX"] += len(re.findall(r"ABRASAX", txt))
    c["ABRAXIS"] += len(re.findall(r"ABRAXIS", txt))
for k, v in c.most_common():
    print(f"  {k:<10} {v}")
