"""Scope audit_config_secrets.py section C to our configuration, not the vendored catch.

The audit scans 19,152 files because CONFIG/agi-config and CONFIG/source-config are
harvested third-party tool trees (C++ headers, PDFs, other tools' settings.json).
Those are not our configuration and scanning them:
  * takes minutes with no progress output
  * is where all the remaining placeholder hits came from

The redactor already learned to skip these directories; the audit has not. Same
drift as the classifier split -- fix both places.

Section A already classifies 1,301 of them as "vendored catch"; section C should
respect that classification instead of re-deciding.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_config_secrets.py"
src = open(PATH, encoding="utf-8").read()

if "SCAN_SKIP" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''targets = []
for base in (os.path.join(ROOT, "CONFIG"), os.path.join(ROOT, "abrasax")):
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fns:
            if fn.endswith((".yaml", ".yml", ".json", ".toml", ".ini", ".py", ".cfg")):
                targets.append(os.path.join(dp, fn))'''

NEW = '''# Harvested third-party tool trees. Section A already classifies these as
# "vendored catch"; section C must respect that instead of re-scanning 19,000
# files that are not our configuration.
SCAN_SKIP = {"agi-config", "source-config"}

targets = []
for base in (os.path.join(ROOT, "CONFIG"), os.path.join(ROOT, "abrasax")):
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__" and d not in SCAN_SKIP]
        for fn in fns:
            if fn.endswith((".yaml", ".yml", ".json", ".toml", ".ini", ".py", ".cfg")):
                targets.append(os.path.join(dp, fn))
print(f"  (skipping vendored trees: {', '.join(sorted(SCAN_SKIP))})", flush=True)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: section C walk")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: section C skips vendored trees")
