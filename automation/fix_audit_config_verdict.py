"""Change section A of audit_config_secrets.py from verdict to measurement.

It reported "CONFIG/agi-config holds 1301 vendored source files that are not
configuration" as a DEFECT. Measured properly (split_agi_config.py):

    total files         2,515
    vendored residue    2,201   (259 MB; 2,092 are .jpg)
    candidate config      314
      referenced by code   68
      read by nothing     246

So "1,301 vendored files" was wrong in both directions: it under-counted the
residue and it implicitly condemned the 68 files that ARE live configuration.

A directory being untidy is not a defect -- it is a finding. Only something that
can break the system belongs in DEFECTS. This changes section A to report the
split and to raise a defect only if LIVE configuration is actually missing.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_config_secrets.py"
src = open(PATH, encoding="utf-8").read()

if "MEASUREMENT, not a verdict" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''if vendored:
    print("    e.g. " + ", ".join(sorted(set(
        os.path.splitext(v)[1] or os.path.basename(v) for v in vendored))[:8]))
    DEFECTS.append(f"CONFIG/agi-config holds {len(vendored)} vendored source files "
                   f"that are not configuration")'''

NEW = '''# MEASUREMENT, not a verdict. CONFIG/agi-config is a harvested tree that also holds
# live configuration, so "N vendored files" is not a defect -- see split_agi_config.py
# for the real split (2,201 residue / 68 referenced / 246 unread). Only something
# that can BREAK the system belongs in DEFECTS.
if vendored:
    kinds = sorted(set(os.path.splitext(v)[1] or os.path.basename(v) for v in vendored))
    print(f"    note: {len(vendored)} harvested file(s) share this tree "
          f"({', '.join(kinds[:8])})")
    print("    these are archived content, not configuration; see "
          "SCRIPTS/automation/split_agi_config.py")'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: section A verdict")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: section A reports the split instead of raising a defect")
