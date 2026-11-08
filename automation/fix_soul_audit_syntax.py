"""Repair the multi-line f-string in audit_soul_fix.py.

The original line 45 was:

    print(f"  checks       : {json.dumps({k: v['checks'][k] for k in v['checks']
                                         if k in ('key_core_matches',)}, default=str)}")

A dict comprehension split across two physical lines inside an f-string is a
SyntaxError: "unterminated string literal". Replaced with straight concatenation,
which has no such restriction.
"""
import re

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_soul_fix.py"
src = open(PATH, encoding="utf-8").read()

# find the broken block and replace it wholesale
start = src.find('print(f"  checks       : {json.dumps(')
if start == -1:
    # maybe a previous partial patch already changed it
    if 'print("  checks       : "' in src:
        print("ALREADY-PATCHED")
        raise SystemExit(0)
    print("ANCHOR-NOT-FOUND")
    raise SystemExit(1)

# consume to the end of the logical statement
end = src.find("\n", src.find("default=str)}", start))
if end == -1:
    end = src.find("\n", start)

replacement = ('print("  checks       : " + str(v["checks"].get("key_core_matches")))')
src = src[:start] + replacement + src[end:]

open(PATH, "w", encoding="utf-8", newline="").write(src)

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("patched and compiled OK")
except py_compile.PyCompileError as e:
    print("still broken:", e)
    for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines()[38:52], 39):
        print(f"  {i}: {line}")
