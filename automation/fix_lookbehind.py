"""Remove the two unused regex lines that break on Python's fixed-width lookbehind.

The patch inserted a helper pattern using a variable-length look-behind:

    JSON_KEY_TAIL = re.compile(r'(?<="\\s*:\\s*)(\\d{4,5})\\b')

Python's `re` requires fixed-width look-behind, so this raises at import:
    re.error: look-behind requires fixed-width pattern

It was never used -- the working logic uses COLON_PORT to find `:NNNN` and
KEY_BEFORE to check the preceding text. Delete both dead lines.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\reconcile_ports.py"
lines = open(PATH, encoding="utf-8").read().splitlines(keepends=True)

out = []
removed = []
for ln in lines:
    s = ln.strip()
    if s.startswith("JSON_KEY_TAIL = re.compile"):
        removed.append(s)
        continue
    if s.startswith("PORT = re.compile(r\"(?<!"):
        removed.append(s)
        continue
    out.append(ln)

if not removed:
    print("nothing to remove (already clean)")
    sys.exit(0)

open(PATH, "w", encoding="utf-8", newline="").write("".join(out))
print(f"removed {len(removed)} dead pattern line(s):")
for r in removed:
    print("  " + r)

# verify it compiles and imports
import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("py_compile FAILED:", e)
    sys.exit(1)
