"""Report real on-disk size of an install tree, ignoring reparse points.

Measure-Object Sum returned 0 for these trees because the launcher uses
directory junctions/hardlinks; counting only real files gives a true number.
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Epic Games"

files = 0
size = 0
skipped = 0
for dp, dirs, fns in os.walk(ROOT, followlinks=False):
    # Prune reparse-point dirs so junctions are not followed twice.
    keep = []
    for d in dirs:
        full = os.path.join(dp, d)
        try:
            if os.path.islink(full) or (os.stat(full).st_file_attributes & 0x400):
                skipped += 1
                continue
        except OSError:
            pass
        keep.append(d)
    dirs[:] = keep
    for fn in fns:
        full = os.path.join(dp, fn)
        try:
            st = os.stat(full)
            size += st.st_size
            files += 1
        except OSError:
            pass

print(f"root      : {ROOT}")
print(f"files     : {files:,}")
print(f"size      : {size:,} bytes  ({size / 1e6:,.1f} MB  /  {size / 2**30:,.2f} GiB)")
print(f"junctions skipped: {skipped}")
sys.exit(0)
