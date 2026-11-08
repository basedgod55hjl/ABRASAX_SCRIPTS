"""Split CONFIG/agi-config into real configuration and harvested residue.

Measured: CONFIG/agi-config is 281 MB and holds BOTH:
  * real configuration this project reads -- agents.yaml, port.yaml,
    abrasax_folder_monitor.yaml, commands.json, completer.json
  * 1,301 vendored files from other projects -- C++ headers (.h/.inl), PDFs,
    SVGs, an AUTHORS file, a copy of cmath

Calling all 1,301 a "defect" is wrong in one direction (the real config is fine)
and unhelpful in the other (it does not say what to do).

This reports the split precisely, lists what is referenced by code, and marks the
rest as move-candidates -- without moving anything. Deleting or relocating another
tool's files is not an audit's call.

Exit 0 always: this produces a report, not a verdict.
"""
import os
import re
import sys

ROOT = r"C:\ABRASAX"
AGI = os.path.join(ROOT, "CONFIG", "agi-config")

if not os.path.isdir(AGI):
    print("CONFIG/agi-config absent -- nothing to split")
    sys.exit(0)

VENDORED_EXT = {".h", ".hpp", ".inl", ".c", ".cpp", ".cc", ".pdf", ".svg",
                ".png", ".jpg", ".ico", ".woff", ".ttf", ".eot", ".map"}
VENDORED_NAMES = {"AUTHORS", "LICENSE", "COPYING", "NOTICE", "cmath", "README",
                  "CMakeLists.txt", "Makefile"}

real, vendored = [], []
for dp, dn, fns in os.walk(AGI):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for fn in fns:
        full = os.path.join(dp, fn)
        try:
            sz = os.path.getsize(full)
        except OSError:
            continue
        rel = os.path.relpath(full, AGI).replace(os.sep, "/")
        ext = os.path.splitext(fn)[1].lower()
        if ext in VENDORED_EXT or fn in VENDORED_NAMES:
            vendored.append((rel, sz))
        else:
            real.append((rel, sz))

print(f"CONFIG/agi-config total files : {len(real) + len(vendored)}")
print(f"  candidate CONFIGURATION     : {len(real)}")
print(f"  vendored residue            : {len(vendored)}")

vbytes = sum(s for _, s in vendored)
print(f"  vendored size               : {vbytes / 1e6:,.1f} MB "
      f"of {sum(s for _, s in real) + vbytes:,.1f} MB")

# which candidate-config files does the code actually reference?
code_roots = [os.path.join(ROOT, "abrasax"),
              os.path.join(ROOT, "SCRIPTS"),
              os.path.join(ROOT, "ENGINE")]
code_text = []
for base in code_roots:
    if not os.path.isdir(base):
        continue
    for dp, dn, fns in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fns:
            if fn.endswith((".py", ".ps1", ".bat", ".md", ".json", ".yaml", ".yml", ".toml")):
                try:
                    if os.path.getsize(os.path.join(dp, fn)) < 2_000_000:
                        code_text.append(open(os.path.join(dp, fn),
                                              encoding="utf-8", errors="ignore").read())
                except OSError:
                    pass
blob = "\n".join(code_text)

referenced, orphaned = [], []
for rel, sz in sorted(real):
    base = os.path.basename(rel)
    if base in blob or rel in blob:
        referenced.append((rel, sz))
    else:
        orphaned.append((rel, sz))

print(f"\n  referenced by code          : {len(referenced)}")
for rel, sz in referenced[:12]:
    print(f"    {rel}  ({sz:,} B)")

print(f"\n  configuration nobody reads  : {len(orphaned)}")
for rel, sz in orphaned[:12]:
    print(f"    {rel}  ({sz:,} B)")
if len(orphaned) > 12:
    print(f"    ... and {len(orphaned) - 12} more")

print("\n--- move candidates (vendored residue, by extension) ---")
from collections import Counter
c = Counter(os.path.splitext(r)[1] or os.path.basename(r) for r, _ in vendored)
for ext, n in c.most_common(10):
    print(f"    {ext or '(no ext)':12s} {n}")

print("\nRECOMMENDATION (not executed -- relocating another tool's files is the")
print("operator's call):")
print(f"  * {len(vendored)} vendored files / {vbytes / 1e6:.0f} MB could move to ARCHIVE/")
print(f"  * {len(orphaned)} configuration files are read by nothing; review them")
print(f"  * {len(referenced)} files are live configuration and should stay")
print("\nRESULT: report produced")
sys.exit(0)
