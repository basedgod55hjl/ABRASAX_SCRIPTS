"""Delete C:\\$WINDOWS.~BT directly. No takeown, no icacls.

We are already in the Administrators role and the deletion does not need a
recursive ACL rewrite (takeown over 106k files ran >12 min without freeing a
byte). shutil.rmtree with an error hook that clears read-only/file flags and
retries once is the correct tool; Windows.old/$WINDOWS.~BT ACLs that truly deny
access will surface as named errors instead of silently succeeding.
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
import time
from pathlib import Path

P = Path("C:/$WINDOWS.~BT")


def free_gb() -> float:
    return shutil.disk_usage("C:/").free / 1e9


def count(root: Path) -> tuple[int, int]:
    n = b = 0
    for dp, _d, fns in os.walk(root):
        for fn in fns:
            try:
                st = (Path(dp) / fn).stat()
            except OSError:
                continue
            n += 1
            b += st.st_size
    return n, b


if not P.exists():
    print("already gone")
    sys.exit(0)

before = free_gb()
n0, b0 = count(P)
print(f"before: {n0} files {b0/1e9:.2f} GB | free {before:.2f} GB")

hard: list[str] = []


def onexc(func, path, exc_info):
    """Clear the read-only bit and retry once; record anything still stuck."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except OSError as exc:
        hard.append(f"{path} -> {type(exc).__name__}: {exc}")


t0 = time.time()
if sys.version_info >= (3, 12):
    shutil.rmtree(P, onexc=onexc)
else:
    shutil.rmtree(P, onerror=lambda f, p, e: onexc(f, p, e))

gone = not P.exists()
after = free_gb()
n1, b1 = count(P) if P.exists() else (0, 0)
print(f"\nelapsed {time.time()-t0:.0f}s")
print(f"deleted: {gone}   remaining: {n1} files {b1/1e9:.2f} GB")
print(f"free: {before:.2f} -> {after:.2f} GB  (reclaimed {after-before:.2f} GB)")
if hard:
    print(f"{len(hard)} stuck, first 8:")
    for h in hard[:8]:
        print("  ", h)
sys.exit(0 if gone else 1)
