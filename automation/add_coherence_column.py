"""Store coherence as its own vertex column so the two locked fractions can agree.

MEASURED
    renderer locked_frac    0.92627
    brain3d  coh_locked_frac 0.1992     <- still 4.6x apart after renaming

The rename was cosmetic because of a structural problem: the vertex buffer stores

    column 4 = glow = base * coherence * breath

Coherence is multiplied by the field activation (`base`, mean 0.498) and a breath
term, so it cannot be recovered by any threshold on column 4. Thresholding the
product answers "how bright is it", never "is it coherent".

THE FIX
    widen the vertex buffer from 6 to 7 floats:
        0..2  pos      3  radius      4  glow      5  charge      6  coherence

    `build_vertices` writes the raw coherence into column 6, and `telemetry` gates on
    it with the renderer's own constant (FB_COH_FLOOR * 0.85 = 0.85), so the two
    numbers measure the same thing by construction.

The shader does not need the new column -- it reads location 0..3 only -- so the
stride change is the only impact: 6*4 -> 7*4 bytes.

`attrs()` is added to brain3d so the GL setup derives its offsets from one place
instead of a hand-written table that could drift from the buffer layout again.
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\ENGINE\floating_brain\brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "VSTRIDE" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# ---- 1. widen the vertex array ----------------------------------------
OLD_ALLOC = "    v = np.zeros((n, 6), dtype=np.float32)"
NEW_ALLOC = ("    # columns: 0..2 pos, 3 radius, 4 glow, 5 charge, 6 coherence\n"
             "    v = np.zeros((n, 7), dtype=np.float32)")
if OLD_ALLOC not in src:
    print("ANCHOR-NOT-FOUND: vertex alloc")
    sys.exit(1)
src = src.replace(OLD_ALLOC, NEW_ALLOC, 1)

# ---- 2. write coherence into column 6 ---------------------------------
OLD_WRITE = "        v[i] = (x, y, z, radius, glow, 0.0)"
NEW_WRITE = ("        # coherence is stored separately from glow: glow is\n"
             "        # base*coh*breath and cannot be un-multiplied back to coherence.\n"
             "        v[i] = (x, y, z, radius, glow, 0.0, min(max(coh, 0.0), 1.0))")
if OLD_WRITE not in src:
    print("ANCHOR-NOT-FOUND: vertex write")
    sys.exit(1)
src = src.replace(OLD_WRITE, NEW_WRITE, 1)

# ---- 3. gate telemetry on the real coherence column -------------------
OLD_GATE = '''    # The coherence gate. The vertex builder stores glow = base*coh*breath, so
    # coherence cannot be recovered from the buffer alone; instead the classic
    # coincidence test is used -- a node is "locked" when its stored glow is at
    # least the field-independent part of what coherence allows. The gate below
    # matches FB_COH_FLOOR * 0.85 applied to a normalised glow.
    coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)'''
NEW_GATE = '''    # The coherence gate, now computed from column 6 which holds raw coherence.
    # The threshold is the renderer's own: FB_COH_FLOOR * 0.85 = 0.85, so the two
    # surfaces measure the same quantity and agree by construction.
    coh = v[:, 6] if v.shape[1] > 6 else None
    if coh is not None:
        coh_locked = float(np.count_nonzero(coh >= 0.85) / coh.size)
    else:  # older 6-column buffer
        coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)'''
if OLD_GATE not in src:
    print("ANCHOR-NOT-FOUND: telemetry gate")
    sys.exit(1)
src = src.replace(OLD_GATE, NEW_GATE, 1)

# ---- 4. single source of truth for GL attribute layout ----------------
OLD_OFF = '''            # interleaved (N,6) float32: pos(3) radius(1) glow(1) charge(1)
            stride = 6 * 4
            OFFSETS = {0: (3, 0), 1: (1, 12), 2: (1, 16), 3: (1, 20)}'''
NEW_OFF = '''            # interleaved (N,7) float32: pos(3) radius glow charge coherence
            stride = VSTRIDE * 4
            OFFSETS = ATTR_OFFSETS'''
if OLD_OFF not in src:
    print("ANCHOR-NOT-FOUND: attribute offsets")
    sys.exit(1)
src = src.replace(OLD_OFF, NEW_OFF, 1)

# ---- 5. define the layout constants near the top ---------------------
OLD_CONST = "NODES = 4096"
NEW_CONST = ("NODES = 4096\n"
             "VSTRIDE = 7          # floats per vertex: pos(3) radius glow charge coherence\n"
             "# attribute location -> (component count, byte offset). Derived from VSTRIDE\n"
             "# so the buffer layout has exactly one definition.\n"
             "def _attr_offsets():\n"
             "    layout = ((0, 3), (1, 1), (2, 1), (3, 1))\n"
             "    out, off = {}, 0\n"
             "    for loc, n in layout:\n"
             "        out[loc] = (n, off)\n"
             "        off += n * 4\n"
             "    return out\n"
             "ATTR_OFFSETS = _attr_offsets()")
if OLD_CONST not in src:
    print("ANCHOR-NOT-FOUND: NODES constant")
    sys.exit(1)
src = src.replace(OLD_CONST, NEW_CONST, 1)

backup = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"patched (backup {backup.rsplit(chr(92),1)[-1]})")

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    sys.exit(1)

print("\nlayout constants:")
for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if any(k in line for k in ("VSTRIDE", "ATTR_OFFSETS", "coh_locked =", "np.zeros((n")):
        print(f"  {i}: {line.strip()[:90]}")
