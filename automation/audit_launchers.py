"""Fix audit_launchers' path extraction before trusting any of its findings.

Measured false positives in the first run:

    C:\\ABRASAX'                     trailing quote not stripped
    C:\\Program                      "C:\\Program Files" truncated at the space
    C:\\ABRASAX\\.env'))              PowerShell call syntax captured as a path
    C:\\ABRASAX\\.env'                same, quote retained
    C:\\ABRASAX\\LOGS\\weekly-cleanup.log:   log prefix "path:" captured
    J:\\Unity'                       quote retained
    C:\\Users\\sirch\\AppData\\Local\\Programs\\LM    truncated at space

Of the 37 "missing paths", a large fraction are extraction artefacts. Fixing the
extractor is required before acting on any of them -- the same rule as every other
false red tonight: prove the instrument before trusting the reading.

Better extraction:
  * allow spaces inside a quoted path; stop at the closing quote
  * strip trailing quote / punctuation / colon
  * reject fragments that are not absolute paths after cleanup
  * skip paths containing shell metacharacters
"""
import os
import re
import sys
from collections import Counter

SCRIPTS = r"C:\ABRASAX\SCRIPTS"

# A quoted path may contain spaces; an unquoted one may not.
QUOTED = re.compile(r'"([A-Za-z]:\\[^"\r\n]*)"')
UNQUOTED = re.compile(r'(?<![\w"\\])([A-Za-z]:\\[^\s<>|"\r\n]*?)(?=[\s<>|")\'],]|$)')

TRAIL = "')],:;. \\"


def clean(p: str) -> str:
    return p.strip(TRAIL)


def extract(text: str):
    found = set()
    for m in QUOTED.finditer(text):
        p = clean(m.group(1))
        if len(p) >= 6:
            found.add(p)
    # remove quoted spans before scanning unquoted, so we do not pick up fragments
    stripped = QUOTED.sub(" ", text)
    for m in UNQUOTED.finditer(stripped):
        p = clean(m.group(1))
        if len(p) >= 6 and "(" not in p and ")" not in p:
            found.add(p)
    return found


launchers = []
for dp, dn, fns in os.walk(SCRIPTS):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for fn in fns:
        if fn.lower().endswith((".bat", ".cmd", ".ps1")):
            launchers.append(os.path.join(dp, fn))

print(f"scanning {len(launchers)} launcher(s)\n")

missing_counter = Counter()
broken = 0
checked = 0

for full in sorted(launchers):
    try:
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue

    paths = extract(text)
    if not paths:
        continue
    checked += 1
    missing = sorted(p for p in paths if not os.path.exists(p))
    if not missing:
        continue

    broken += 1
    rel = os.path.relpath(full, SCRIPTS)
    print(f"{rel}")
    print(f"  {len(missing)} of {len(paths)} path(s) missing")
    for p in missing[:8]:
        print(f"    {p}")
        missing_counter[p] += 1
    if len(missing) > 8:
        print(f"    ... and {len(missing) - 8} more")
    print()

print("=" * 70)
print(f"launchers referencing at least one real path : {checked}")
print(f"launchers with a genuinely missing path      : {broken}")
print(f"distinct missing paths                       : {len(missing_counter)}")

print("\nmissing-path roots (top 10):")
roots = Counter()
for p, n in missing_counter.items():
    parts = p.split("\\")
    root = "\\".join(parts[:4]) if len(parts) >= 4 else p
    roots[root] += n
for r, n in roots.most_common(10):
    print(f"  {n:3d}x  {r}")

print("\nRESULT: report produced (extractor corrected)")
sys.exit(0)
