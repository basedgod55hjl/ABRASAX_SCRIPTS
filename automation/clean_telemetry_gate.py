"""Remove the stacked duplicate that the merged patches left in telemetry().

Lines 289-298 currently contain BOTH an older gate and the newer one, interleaved,
which is why Python reports an IndentationError after the `else:` on 295.

Kept:  lines 296-301 are logically right (gate on column 6, proxy fallback)
Dropped: the stale block 289-295

Written as an explicit line-range splice so the result is exactly known, then
verified by compiling and by checking that only ONE `coh_locked =` assignment
survives at the top level.
"""
import shutil
import time

PATH = r"C:\ABRASAX\ENGINE\floating_brain\brain3d.py"
lines = open(PATH, encoding="utf-8").read().splitlines(keepends=True)

# locate the region: from the stale comment to the line before the good gate
start = None
for i, ln in enumerate(lines):
    if "The coherence gate, now computed from column 6" in ln:
        start = i
        break
if start is None:
    print("ANCHOR-NOT-FOUND: stale comment")
    raise SystemExit(1)

# the good block starts at the line beginning with 4 spaces + "if v.shape[1] > 6:"
good = None
for i in range(start, min(start + 20, len(lines))):
    if lines[i].startswith("    if v.shape[1] > 6:"):
        good = i
        break
if good is None:
    print("ANCHOR-NOT-FOUND: good gate")
    raise SystemExit(1)

replacement = [
    "    # Gate on column 6 (raw coherence) with the renderer's own constant\n",
    "    # FB_COH_FLOOR*0.85 = 0.85, so both surfaces measure the same quantity.\n",
]

new_lines = lines[:start] + replacement + lines[good:]
src = "".join(new_lines)

backup = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"spliced out {good - start} stale line(s); backup {backup.rsplit(chr(92),1)[-1]}")

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    for i, ln in enumerate(open(PATH, encoding="utf-8").read().splitlines()[284:305], 285):
        print(f"  {i}: {ln}")

# confirm exactly one gate remains
body = open(PATH, encoding="utf-8").read()
n_gate = body.count("v[:, 6] >= 0.85")
n_proxy = body.count("glow >= 0.85 * 0.45")
print(f"\ncolumn-6 gates: {n_gate}   proxy gates: {n_proxy}")
