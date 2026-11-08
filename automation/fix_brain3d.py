"""Fix two real defects in brain3d.py before running it.

1  MISSING IMPORT
   `_program` and the attribute setup reference `ctypes.c_void_p` but the module
   never imports ctypes. Would raise NameError on the first draw.

2  WRONG ATTRIBUTE OFFSETS
   The pointer arithmetic was a nested ternary that computed the wrong byte offset
   for each attribute. For an interleaved (N,6) float32 buffer the offsets must be
   exactly loc*4 per float slot:

       loc 0  a_pos     offset  0   size 3
       loc 1  a_radius  offset 12   size 1
       loc 2  a_glow    offset 16   size 1
       loc 3  a_charge  offset 20   size 1

   A wrong offset feeds the shader position data where radius should be, which
   produces garbage geometry that still "runs" -- the worst kind of bug.

This rewrites the import block and the attribute loop correctly.
"""
import sys

PATH = r"C:\ABRASAX\ENGINE\floating_brain\brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "import ctypes" in src and "OFFSETS = " in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# --- 1. add the ctypes import next to numpy -----------------------------
src = src.replace("import numpy as np\n", "import ctypes\n\nimport numpy as np\n", 1)

# --- 2. replace the attribute setup with explicit correct offsets -------
old = """            stride = 6 * 4
            for loc, size in ((0, 3), (1, 1), (2, 1), (3, 1)):
                glEnableVertexAttribArray(loc)
                glVertexAttribPointer(loc, size, GL_FLOAT, False, stride,
                                      ctypes.c_void_p(loc * 0 if loc == 0 else (8 if loc == 1 else (12 if loc == 2 else 16))))"""

new = """            # interleaved (N,6) float32: pos(3) radius(1) glow(1) charge(1)
            stride = 6 * 4
            OFFSETS = {0: (3, 0), 1: (1, 12), 2: (1, 16), 3: (1, 20)}
            for loc in (0, 1, 2, 3):
                size, offset = OFFSETS[loc]
                glEnableVertexAttribArray(loc)
                glVertexAttribPointer(loc, size, GL_FLOAT, False, stride,
                                      ctypes.c_void_p(offset))"""

if old not in src:
    print("ANCHOR-NOT-FOUND: attribute setup")
    print("searching for a close match ...")
    for i, line in enumerate(src.splitlines(), 1):
        if "glVertexAttribPointer" in line:
            print(f"  {i}: {line.strip()}")
    sys.exit(1)

src = src.replace(old, new, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("patched; py_compile OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    sys.exit(1)

for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if "OFFSETS" in line or "import ctypes" in line or "c_void_p(offset)" in line:
        print(f"  {i}: {line.strip()}")
