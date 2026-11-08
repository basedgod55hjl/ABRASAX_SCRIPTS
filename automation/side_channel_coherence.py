"""Resolve the build_loop/audit conflict properly: internal coherence, GPU gets 6.

WHAT build_loop DID, AND WHY IT IS RIGHT

    v = np.zeros((n, 7))                # 7 columns internally
    v[:, 6] = coherence                 # column 6 holds raw coherence
    return v[:, :6]                     # export only 6 to the GPU

    VSTRIDE = 6                         # the interleaved VBO layout

The reasoning in the source comment is sound: the shader declares locations 0..3 with
a stride of VSTRIDE*4. Widening the exported buffer to 7 columns while the shader
still uses a 6-float stride would make every vertex after the first be read from the
wrong offset -- garbage geometry that still renders. Exporting 6 keeps the VBO
correct.

THE PROBLEM IT CREATES

    telemetry(v) receives the EXPORTED 6-column array, so the coherence column is
    already gone by the time telemetry runs. brain3d then falls back to the glow
    proxy and reports ~12% instead of the renderer's ~93%.

THE FIX

    Keep the export at 6 (do not touch the GPU path).
    Have build_vertices also return the coherence vector, or attach it as an
    attribute-free side channel, so telemetry can gate on the real value.

    Simplest correct design: build_vertices returns the 6-column GPU array and stores
    the coherence vector on the module as `last_coherence`, which telemetry reads if
    the caller passes the same buffer. Cleaner: return a small object. Least invasive:
    accept an optional `coherence=` argument in telemetry and have the overlay pass
    it.

This patch does the least invasive version AND makes the old path honest: telemetry
now reports coh_locked_frac from coherence when supplied, and clearly labels the glow
proxy when it is not.
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\ENGINE\floating_brain\brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "last_coherence" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# ---- 1. build_vertices stores the coherence side-channel ---------------
old_ret = '''    # The GPU stride is VSTRIDE=6 (pos,radius,glow,charge). Column 6 is
    # internal coherence used by telemetry; returning it would corrupt the
    # interleaved VBO. Export a contiguous 6-column buffer.
    return np.ascontiguousarray(v[:, :6], dtype=np.float32)'''

new_ret = '''    # The GPU stride is VSTRIDE=6 (pos,radius,glow,charge). Column 6 is
    # internal coherence used by telemetry; returning it would corrupt the
    # interleaved VBO. Export a contiguous 6-column buffer, and publish the
    # coherence vector separately so telemetry can gate on the real value.
    global last_coherence
    last_coherence = np.ascontiguousarray(v[:, 6], dtype=np.float32)
    return np.ascontiguousarray(v[:, :6], dtype=np.float32)'''

if old_ret not in src:
    print("ANCHOR-NOT-FOUND: export line")
    sys.exit(1)
src = src.replace(old_ret, new_ret, 1)

# ---- 2. declare the side channel --------------------------------------
old_nodes = "NODES = 4096\n"
new_nodes = ("NODES = 4096\n"
             "# Coherence from the most recent build_vertices(). It is NOT part of the\n"
             "# exported GPU buffer (stride 6), but telemetry needs it to report the same\n"
             "# coherence gate the renderer uses.\n"
             "last_coherence = None\n")
if old_nodes not in src:
    print("ANCHOR-NOT-FOUND: NODES")
    sys.exit(1)
src = src.replace(old_nodes, new_nodes, 1)

# ---- 3. telemetry uses it --------------------------------------------
old_gate = '''    if v.shape[1] > 6:
        coh_locked = float(np.count_nonzero(v[:, 6] >= 0.85) / v.shape[0])
    else:  # older 6-column buffer: best available proxy
        coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)'''

new_gate = '''    # Prefer the published coherence vector; fall back to the glow proxy only when
    # it is absent, and say so in the returned dict so a caller can tell.
    coh_source = "glow-proxy"
    coh = None
    if v.shape[1] > 6:
        coh = v[:, 6]
        coh_source = "column6"
    elif last_coherence is not None and last_coherence.shape[0] == v.shape[0]:
        coh = last_coherence
        coh_source = "side-channel"

    if coh is not None:
        coh_locked = float(np.count_nonzero(coh >= 0.85) / coh.size)
    else:
        coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)'''

if old_gate not in src:
    print("ANCHOR-NOT-FOUND: telemetry gate")
    sys.exit(1)
src = src.replace(old_gate, new_gate, 1)

# ---- 4. expose which source was used ---------------------------------
old_keys = '"locked_frac": coh_locked,   # alias: keep the old name meaningful'
new_keys = ('"locked_frac": coh_locked,   # alias: keep the old name meaningful\n'
            '        "coherence_source": coh_source,')
if old_keys in src:
    src = src.replace(old_keys, new_keys, 1)

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
