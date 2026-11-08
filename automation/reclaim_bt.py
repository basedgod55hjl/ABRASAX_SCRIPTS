"""Reclaim C:\\$WINDOWS.~BT -- the abandoned Windows Setup sandbox.

Evidence this is safe to remove (measured, not assumed):
  * HKLM\\SYSTEM\\Setup SystemSetupInProgress=0, SetupType=0, OOBEInProgress=0
  * No SetupHost / SetupPlatform / WinSetup process running
  * No RebootRequired / RebootPending keys
  * Sources\\Panther\\setupact.log ends 2026-08-04 08:44:58 with
    CSetupManager::Execute Result = 0x800704C7  (ERROR_CANCELLED)
  * Last write anywhere in the tree: 2026-08-04, i.e. ~2.5 months stale
  * OS installed 2026-07-25, build 26200, no completed upgrade since

Windows keeps this only to resume/roll back an in-flight upgrade. There is none.

Approach: this tree is highly compressible (4.5 GB of setup sources), so it is
stream-reported then deleted. Deletion needs ownership/ACL work because Windows
Sets ACLs that deny even administrators, hence the takeown/icacls fallback.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

P = Path("C:/$WINDOWS.~BT")


def free_gb() -> float:
    return shutil.disk_usage("C:/").free / 1e9


def size_of(root: Path) -> tuple[int, int]:
    n = b = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            try:
                st = (Path(dirpath) / fn).stat()
            except OSError:
                continue
            n += 1
            b += st.st_size
    return n, b


if not P.exists():
    print("already gone:", P)
    sys.exit(0)

before = free_gb()
n, b = size_of(P)
print(f"target {P}: {n} files, {b/1e9:.2f} GB")
print(f"free before: {before:.2f} GB")

# 1. take ownership + grant ourselves full control (Windows Sets denies admins)
print("\n[1/3] takeown /f /r /d y")
r = subprocess.run(["takeown", "/f", str(P), "/r", "/d", "y"],
                   capture_output=True, text=True)
print("  rc:", r.returncode, "|", (r.stdout or r.stderr).strip().splitlines()[-1:] or "")

print("[2/3] icacls grant")
r = subprocess.run(["icacls", str(P), "/grant", f"{os.environ.get('USERNAME','*S-1-5-32-544')}:F",
                    "/t", "/c", "/q"], capture_output=True, text=True)
print("  rc:", r.returncode)

# 3. delete
print("[3/3] removing")
errors = []


def onerr(func, path, exc):
    errors.append(f"{path}: {exc[1]}")


shutil.rmtree(P, onerror=onerr)

still = P.exists()
after = free_gb()
print(f"\ndeleted: {not still}")
print(f"free after: {after:.2f} GB  (reclaimed {(after - before):.2f} GB)")
if errors:
    print(f"{len(errors)} errors; first 5:")
    for e in errors[:5]:
        print("   ", e)
sys.exit(0 if not still else 1)
