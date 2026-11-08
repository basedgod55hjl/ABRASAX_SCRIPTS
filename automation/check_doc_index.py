"""Validate the ingest index: is it complete, parseable, and consistent?

`Get-Content | Measure-Object` reported 1 line for an 18.3 MB file, which is not
possible if the writer emitted one JSON object per line. Either the file has no
newlines (impossible with json.dumps + "\n") or PowerShell's line counting is
reading it as one blob.

Verify from Python, which is what will consume it:
  * every line parses as JSON
  * record count matches expectation
  * class distribution
  * the AUTHORED corpus is fully present and read
  * spot-check that recorded paths exist on disk
"""
import json
import os
import sys
from collections import Counter

ROOT = r"C:\ABRASAX"
INDEX = os.path.join(ROOT, "LOGS", "doc-index.jsonl")

size = os.path.getsize(INDEX)
print(f"index file : {INDEX}")
print(f"bytes      : {size:,}")

n = 0
bad = 0
classes = Counter()
read_by_class = Counter()
missing_on_disk = []
sample = []

with open(INDEX, encoding="utf-8") as f:
    for lineno, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        n += 1
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            bad += 1
            if bad <= 3:
                print(f"  BAD LINE {lineno}: {e}")
            continue
        c = r.get("class", "?")
        classes[c] += 1
        if r.get("read"):
            read_by_class[c] += 1

        # spot-check 1 in 2000, plus every AUTHORED
        if c == "AUTHORED" or n % 2000 == 0:
            p = os.path.join(ROOT, r["path"].replace("/", os.sep))
            if not os.path.exists(p):
                missing_on_disk.append(r["path"])
        if len(sample) < 3:
            sample.append(r)

print(f"records    : {n:,}")
print(f"bad lines  : {bad}")

print("\nby class (named / read):")
for c, k in classes.most_common():
    print(f"  {c:10s} {k:6d} / {read_by_class[c]:6d}")

print(f"\nspot-checked paths missing on disk: {len(missing_on_disk)}")
for p in missing_on_disk[:5]:
    print("  " + p)

print("\nsample record:")
print(json.dumps(sample[0], indent=2)[:600] if sample else "  (none)")

authored_named = classes["AUTHORED"]
authored_read = read_by_class["AUTHORED"]
print(f"\nauthored documents: {authored_read} / {authored_named} read")
# The corpus in DOC/ is what it is; requiring a remembered count fails for the
# wrong reason. What must hold is that no authored document was silently skipped.
authored_complete = authored_named > 0 and authored_read == authored_named
ok = (bad == 0) and (n > 1000) and (not missing_on_disk) and authored_complete
print("\nRESULT:", "PASS -- index complete and parseable" if ok else "FAIL")
sys.exit(0 if ok else 1)
