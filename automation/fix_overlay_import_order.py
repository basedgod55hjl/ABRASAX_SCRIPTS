"""Fix an import-order crash introduced by the brain3d overlay patch.

The patch inserted its block immediately after `import glfw / import imgui`, but the
file imports `os` further down:

    NameError: name 'os' is not defined
      File ".../imgui_overlay.py", line 41, in <module>
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

The brain3d import must run AFTER the stdlib imports the overlay already has. Moving
the whole patch block to after the last top-level import fixes it, and keeps the
block text identical so the marker still works.
"""
import re
import sys

PATH = r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py"
MARK = "# ---- BRAIN3D MODE (patch) ----"

src = open(PATH, encoding="utf-8").read()

if "import os\n" in src.split(MARK)[0]:
    print("ALREADY-FIXED: os is imported before the patch block")
    sys.exit(0)

# locate the patch block (from the marker through the except clause)
start = src.find(MARK)
if start == -1:
    print("ANCHOR-NOT-FOUND: patch marker")
    sys.exit(1)

end_marker = "    _B3D_IMPORT_ERROR = str(_e)\n"
end = src.find(end_marker, start)
if end == -1:
    print("ANCHOR-NOT-FOUND: patch block end")
    sys.exit(1)
end += len(end_marker)

block = src[start:end]
# remove it, and the blank line the patch left behind
rest = src[:start] + src[end:]
rest = rest.replace("import imgui\n\n\n", "import imgui\n")

# find the last top-level import line to insert after
lines = rest.splitlines(keepends=True)
last_import = 0
for i, ln in enumerate(lines[:80]):
    if re.match(r"^(import |from )\w", ln):
        last_import = i

lines.insert(last_import + 1, "\n" + block)
fixed = "".join(lines)

open(PATH, "w", encoding="utf-8", newline="").write(fixed)

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("patched; py_compile OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    sys.exit(1)

# show the import region so the ordering is visible
for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines()[:50], 1):
    if line.startswith(("import", "from", "# ----")) or "sys.path.insert" in line:
        print(f"  {i:3d}: {line}")
