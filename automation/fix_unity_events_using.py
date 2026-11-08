"""Add the missing `using UnityEngine.Events;` to FloatingBrainRenderer.cs.

Found by the real Unity compiler, not by the Roslyn stub check:

    FloatingBrainRenderer.cs(82,16): error CS0246: The type or namespace name
    'UnityEvent' could not be found

UnityEvent lives in UnityEngine.Events, a namespace my minimal stub file did not
model (BrainHUD.cs presumably imports it, which is why the existing scripts build).
This is the second time Unity caught something the stub missed -- the stub proves
syntax and symbol shape, not the real Unity API surface.

Idempotent.
"""
import sys

# Paths come from one resolver so a script cannot open the wrong tree.
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
from abra_paths import paths  # noqa: E402

PATH = r"C:\ABRASAX\APPS\unity-assets\BrainUI\Scripts\FloatingBrainRenderer.cs"
TARGET = str(paths.unity_scripts)

for p in (PATH, TARGET):
    try:
        src = open(p, encoding="utf-8").read()
    except OSError as e:
        print(f"skip {p}: {e}")
        continue

    if "using UnityEngine.Events;" in src:
        print(f"ALREADY-PATCHED {p}")
        continue

    anchor = "using UnityEngine;\n"
    if anchor not in src:
        print(f"ANCHOR-NOT-FOUND {p}")
        sys.exit(1)

    src = src.replace(anchor, anchor + "using UnityEngine.Events;\n", 1)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    print(f"PATCHED {p}")

print("\nusings now:")
for line in open(PATH, encoding="utf-8"):
    if line.startswith("using "):
        print("  " + line.strip())
