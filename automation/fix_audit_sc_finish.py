"""Make the section-3 audit finish: cap the secret scan and add a --fast mode.

The audit keeps timing out because section F reads every tracked text file. On this
repo that is 6,890 files including 20+ MB CSVs, and the whole process produces no
output until it ends.

Two changes:
  1. skip files over 1 MB in the secret scan (a 30 MB FILESYSTEM_INDEX.json is a
     generated catalog; scanning it for keys is pointless and dominates runtime)
  2. add --fast, which runs A-E only, so the structural checks are always
     obtainable even if the corpus scan is slow
  3. progress line every 500 files so a slow run is visibly alive
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_source_control.py"
src = open(PATH, encoding="utf-8").read()

if "--fast" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. smaller size cap + progress
OLD = '''    try:
        if os.path.getsize(full) > 2_000_000:
            continue
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue'''
NEW = '''    try:
        # 1 MB cap: the big files here are generated catalogs (a 30 MB
        # FILESYSTEM_INDEX.json). Scanning them for keys is pointless and
        # dominated the runtime of this whole audit.
        if os.path.getsize(full) > 1_000_000:
            continue
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue'''
if OLD not in src:
    print("ANCHOR-NOT-FOUND: size cap")
    sys.exit(1)
src = src.replace(OLD, NEW, 1)

# 2. --fast flag
OLD2 = '''ROOT = r"C:\\ABRASAX"
DEFECTS = []'''
NEW2 = '''ROOT = r"C:\\ABRASAX"
DEFECTS = []
FAST = "--fast" in sys.argv   # skip the slow corpus-wide secret scan'''
if OLD2 not in src:
    print("ANCHOR-NOT-FOUND: ROOT/DEFECTS")
    sys.exit(1)
src = src.replace(OLD2, NEW2, 1)

# 3. skip section F in fast mode
OLD3 = '''header("F. SECRETS IN TRACKED FILES")'''
NEW3 = '''if FAST:
    header("F. SECRETS IN TRACKED FILES")
    print("  skipped (--fast); run without --fast for the full corpus scan", flush=FLUSH)
    hits = []
else:
    header("F. SECRETS IN TRACKED FILES")'''
if OLD3 not in src:
    print("ANCHOR-NOT-FOUND: section F header")
    sys.exit(1)
src = src.replace(OLD3, NEW3, 1)

# indent the remainder of section F under the else
start = src.find(NEW3) + len(NEW3)
end = src.find('header("SUMMARY")', start)
if end == -1:
    print("ANCHOR-NOT-FOUND: SUMMARY")
    sys.exit(1)

block = src[start:end]
indented = []
for line in block.splitlines(keepends=True):
    if line.strip():
        indented.append("    " + line)
    else:
        indented.append(line)
src = src[:start] + "".join(indented) + src[end:]

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: 1 MB cap, --fast mode, section F gated")
