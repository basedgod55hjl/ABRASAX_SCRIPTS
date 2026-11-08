"""Find the 3 archives the checker says are bad, with the real exception text.

check_tree_organised.py reported:
    [FAIL] every archive decompresses — 3 bad of 61
but a standalone loop over the same directory found zero failures. One of the two
is wrong, and the difference has to be pinned down rather than guessed at.

This prints, for every .gz under LOGS/archive:
    path, gz size, decompressed size, or the exact exception
"""
import gzip
import os

A = r"C:\ABRASAX\LOGS\archive"

paths = []
for dp, _dn, fns in os.walk(A):
    for fn in fns:
        if fn.endswith(".gz"):
            paths.append(os.path.join(dp, fn))

print(f"found {len(paths)} .gz file(s)\n")

problems = []
for p in sorted(paths):
    gzsize = os.path.getsize(p)
    try:
        with gzip.open(p, "rb") as f:
            data = f.read()
        raw = len(data)
        if raw == 0 and gzsize < 40:
            problems.append((p, f"decompresses to 0 bytes from {gzsize} B"))
            print(f"  EMPTY  {os.path.basename(p):60s} gz={gzsize:6d} raw=0")
    except OSError as e:
        problems.append((p, f"{type(e).__name__}: {e}"))
        print(f"  ERROR  {os.path.basename(p):60s} gz={gzsize:6d}  {type(e).__name__}: {e}")

print(f"\nproblems: {len(problems)}")
for p, why in problems:
    print(f"  {p}\n      {why}")

# Also list files that are NOT .gz in the archive dir -- the checker counts only
# .gz, so a stray file there would be invisible to both.
stray = []
for dp, _dn, fns in os.walk(A):
    for fn in fns:
        if not fn.endswith(".gz"):
            stray.append(os.path.join(dp, fn))
print(f"\nnon-.gz files in archive dir: {len(stray)}")
for s in stray[:10]:
    print("  " + os.path.relpath(s, A))
