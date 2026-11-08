"""Retire the abandoned Library on J: without destroying evidence.

MEASURED: J:\\UnityProjects\\ABRASAX-Brain\\Library holds 839 files but
ScriptAssemblies/ is EMPTY -- that tree never completed a compile. It is residue
from build attempts made before the project moved to C: (see DOC/UNITY-BUILD.md
F4: J: is a USB HDD and Library is thousands of small files).

Keeping it breaks the role split: J: is supposed to be the SOURCE tree (Assets,
Packages, ProjectSettings) and C: the build workspace (Library). Two Library trees
means a script can open the wrong one and see stale state -- which is exactly the
race that faked a regression earlier.

This does NOT delete. It moves the abandoned tree to an archive location first, so
the claim "never compiles" stays checkable, then reports what remains.

Idempotent: if the J: Library is already gone it exits quietly.
"""
import os
import shutil
import sys
import time
from pathlib import Path

SRC = Path(r"J:\UnityProjects\ABRASAX-Brain\Library")
ARCHIVE_ROOT = Path(r"J:\ABRASAX-ARCHIVE\unity-library-abandoned")
DEST = ARCHIVE_ROOT / ("Library-" + time.strftime("%Y%m%d-%H%M"))

apply = "--apply" in sys.argv


def count(root: Path):
    if not root.exists():
        return 0, 0
    n = sz = 0
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            try:
                n += 1
                sz += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return n, sz


if not SRC.exists():
    print("J: Library already absent -- nothing to retire")
    sys.exit(0)

n, sz = count(SRC)
print(f"J: Library      : {SRC}")
print(f"  files         : {n:,}")
print(f"  bytes         : {sz:,} ({sz / 1e6:.1f} MB)")

asm = SRC / "ScriptAssemblies"
asm_count = len(list(asm.iterdir())) if asm.exists() else -1
print(f"  ScriptAssemblies entries: {asm_count}")
if asm_count == 0:
    print("  -> never compiled; safe to retire")
else:
    print("  -> WARNING: contains assemblies; review before retiring")

# what does the BUILD tree look like, for comparison?
build_lib = Path(r"C:\UnityProjects\ABRASAX-Brain\Library")
bn, bsz = count(build_lib)
print(f"\nC: Library (live): {bn:,} files, {bsz / 1e6:.1f} MB")
print(f"  C: ScriptAssemblies exists: {(build_lib / 'ScriptAssemblies').exists()}")

if not apply:
    print(f"\ndry run. With --apply this would MOVE the J: Library to\n  {DEST}")
    print("Nothing is deleted; the archive keeps the evidence that this tree never built.")
    sys.exit(0)

DEST.parent.mkdir(parents=True, exist_ok=True)
print(f"\nmoving to {DEST} ...")
shutil.move(str(SRC), str(DEST))

print("moved.")
print(f"  J: Library present now : {SRC.exists()}")
print(f"  archived at            : {DEST}")
sys.exit(0)
