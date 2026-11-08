"""Merge two fixes that overwrote each other.

TIMELINE
  my edit      widened the buffer to 7 columns and stored raw coherence in column 6,
               so brain3d's `locked_frac` could match the renderer's coherence gate
  build_loop's replaced build_vertices, kept the buffer at 6 columns "for byte-for-byte
               compatibility with the original caller", added a 98th-percentile
               fallback for the defect layer, and recomputed the locked fraction from
               glow instead

BOTH improvements are real and neither should be lost:
  * the 98th-percentile fallback fixes a genuine bug -- the live field's Laplacian
    maxes at 0.1108, so the hard 0.45 threshold can NEVER fire and the defect layer
    was silently empty
  * the coherence column fixes a genuine mislabel -- glow is base*coh*breath and
    cannot be un-multiplied, so gating on it reported 12% while the field was 92.6%
    coherent

MERGED RESULT
  buffer       (N, 7): pos3 radius glow charge coherence
  defects      98th-percentile fallback retained
  telemetry    coh_locked_frac gates on column 6 with the renderer's 0.85 constant
  shader       unaffected -- it reads locations 0..3, so a wider stride is invisible
               to it as long as ATTR_OFFSETS is derived, not hand-written
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\ENGINE\floating_brain\brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "VSTRIDE" in src and "coh_locked" in src and "np.zeros((n, 7)" in src:
    print("ALREADY-MERGED")
    sys.exit(0)

# ---- 1. widen to 7 columns --------------------------------------------
if "np.zeros((n, 7)" not in src:
    old = "    v = np.zeros((n, 6), dtype=np.float32)"
    new = ("    # columns: 0..2 pos, 3 radius, 4 glow, 5 charge, 6 coherence\n"
           "    # coherence is stored separately because glow = base*coh*breath and\n"
           "    # cannot be un-multiplied back to coherence by any threshold.\n"
           "    v = np.zeros((n, 7), dtype=np.float32)")
    if old not in src:
        print("ANCHOR-NOT-FOUND: vertex alloc")
        sys.exit(1)
    src = src.replace(old, new, 1)

# ---- 2. write coherence in the per-node loop --------------------------
old_w = "        v[i] = (x, y, z, radius, glow, 0.0)"
new_w = ("        v[i] = (x, y, z, radius, glow, 0.0,\n"
         "                min(max(coh, 0.0), 1.0))")
if old_w in src:
    src = src.replace(old_w, new_w, 1)
elif "min(max(coh, 0.0), 1.0))" not in src:
    print("ANCHOR-NOT-FOUND: vertex write")
    sys.exit(1)

# ---- 3. layout constants ----------------------------------------------
if "VSTRIDE" not in src:
    old_c = "NODES = 4096"
    new_c = ("NODES = 4096\n"
             "VSTRIDE = 7          # pos(3) radius glow charge coherence\n"
             "def _attr_offsets():\n"
             "    out, off = {}, 0\n"
             "    for loc, n in ((0, 3), (1, 1), (2, 1), (3, 1)):\n"
             "        out[loc] = (n, off)\n"
             "        off += n * 4\n"
             "    return out\n"
             "ATTR_OFFSETS = _attr_offsets()")
    if old_c not in src:
        print("ANCHOR-NOT-FOUND: NODES")
        sys.exit(1)
    src = src.replace(old_c, new_c, 1)

# ---- 4. GL attribute setup derives from the table --------------------
src = src.replace(
    "            stride = 6 * 4\n"
    "            OFFSETS = {0: (3, 0), 1: (1, 12), 2: (1, 16), 3: (1, 20)}",
    "            stride = VSTRIDE * 4\n"
    "            OFFSETS = ATTR_OFFSETS")

# ---- 5. telemetry gates on the real coherence column -----------------
old_gate = "    coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)"
new_gate = ("    # Gate on column 6 (raw coherence) with the renderer's own constant\n"
            "    # FB_COH_FLOOR*0.85 = 0.85, so both surfaces measure the same quantity.\n"
            "    if v.shape[1] > 6:\n"
            "        coh_locked = float(np.count_nonzero(v[:, 6] >= 0.85) / v.shape[0])\n"
            "    else:  # older 6-column buffer: best available proxy\n"
            "        coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)")
if old_gate in src:
    src = src.replace(old_gate, new_gate, 1)
elif "v[:, 6] >= 0.85" not in src:
    print("ANCHOR-NOT-FOUND: telemetry gate")
    sys.exit(1)

backup = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"merged (backup {backup.rsplit(chr(92),1)[-1]})")

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    sys.exit(1)

print("\nkey lines:")
for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if any(k in line for k in ("VSTRIDE = ", "ATTR_OFFSETS = ", "np.zeros((n, 7)",
                               "v[:, 6] >= 0.85", "percentile")):
        print(f"  {i}: {line.strip()[:88]}")
