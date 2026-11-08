"""Set Unity's productName to a space-free value and back up the original.

Evidence: the editor stalls on

    [MODES] Loading mode Default (0) for mode-current-id-ABRASAX Brain

i.e. the mode id is derived from productName, which is "ABRASAX Brain". This is
Unity 7000.0.0a10 (alpha); a space in the mode id is a plausible stall, and it is
cheap to test. Nothing else is changed.

Idempotent. Always writes a .bak- before the first modification.
"""
import shutil
import sys

# Paths come from one resolver so a script cannot open the wrong tree.
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
from abra_paths import paths  # noqa: E402

PATH = str(paths.unity_settings / 'ProjectSettings.asset')
BAK = PATH + ".bak-20261018"

src = open(PATH, encoding="utf-8").read()

if "productName: ABRASAXBrain" in src:
    print("ALREADY-PATCHED: productName is already ABRASAXBrain")
else:
    if "productName: ABRASAX Brain" not in src:
        print("ANCHOR-NOT-FOUND: 'productName: ABRASAX Brain'")
        sys.exit(1)
    shutil.copy2(PATH, BAK)
    src = src.replace("productName: ABRASAX Brain", "productName: ABRASAXBrain")
    with open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    print(f"PATCHED: productName -> ABRASAXBrain (backup {BAK.rsplit(chr(92), 1)[-1]})")

for line in open(PATH, encoding="utf-8"):
    if "productName" in line or "companyName" in line:
        print("  " + line.strip())
