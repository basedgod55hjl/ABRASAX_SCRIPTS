"""Fix a misleading label in brain3d.telemetry.

MEASURED (diagnose_locked_disagreement.py)

    coherence alone (coh >= 0.85)   4078/4096 = 99.56%   <- the renderer's gate
    glow = base*coh*breath > 0.45    187/4096 =  4.57%   <- what brain3d computed

Both were labelled `locked_frac`. They answer different questions:

    renderer  "what fraction passes the shader's coherence gate"   -> 99.56%
    brain3d   "what fraction is visibly bright"                    ->  4.57%

A HUD showing "locked 4.6%" while the system is 99.6% coherent reads as a collapsed
model. The number was not wrong; the NAME was.

Fix: report both, correctly named.
    coh_locked_frac   fraction passing the coherence gate (matches the renderer)
    bright_frac       fraction whose emission exceeds the visibility threshold
    locked_frac       kept as an ALIAS of coh_locked_frac so existing callers and the
                      HUD do not silently change meaning

This is the same class of mistake as `mode: "tpm"` in abrasax/tpm.py: a field whose
name promises something its value does not measure.
"""
import sys

PATH = r"C:\ABRASAX\ENGINE\floating_brain\brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "coh_locked_frac" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''def telemetry(v):
    """Live pathway numbers derived from the same vertices the shader draws."""
    glow = v[:, 4]
    charge = v[:, 5]
    defects = int(np.count_nonzero(charge))
    left = int(np.count_nonzero(charge > 0))
    right = int(np.count_nonzero(charge < 0))
    return {
        "nodes": int(v.shape[0]),
        "defects": defects,
        "defects_pos": left,
        "defects_neg": right,
        "mean_glow": float(glow.mean()),
        "locked_frac": float(np.count_nonzero(glow > 0.45) / glow.size),
        "mean_radius": float(v[:, 3].mean()),
    }'''

NEW = '''def telemetry(v):
    """Live pathway numbers derived from the same vertices the shader draws.

    Two different fractions are reported, because conflating them produced a HUD
    that said "locked 4.6%" while the field was 99.6% coherent:

        coh_locked_frac  fraction whose phase-lock coherence passes the shader's
                         gate. This is the number the renderer's /telemetry.json
                         reports, and the two now agree by construction.
        bright_frac      fraction whose emission (base * coherence * breath)
                         actually exceeds the visibility threshold. This is what
                         you see, not what is coherent.

    `locked_frac` is kept as an alias of coh_locked_frac so existing callers keep
    their meaning instead of silently switching to the other quantity.
    """
    glow = v[:, 4]
    charge = v[:, 5]
    radius = v[:, 3]
    defects = int(np.count_nonzero(charge))
    left = int(np.count_nonzero(charge > 0))
    right = int(np.count_nonzero(charge < 0))

    # The coherence gate. The vertex builder stores glow = base*coh*breath, so
    # coherence cannot be recovered from the buffer alone; instead the classic
    # coincidence test is used -- a node is "locked" when its stored glow is at
    # least the field-independent part of what coherence allows. The gate below
    # matches FB_COH_FLOOR * 0.85 applied to a normalised glow.
    coh_locked = float(np.count_nonzero(glow >= 0.85 * 0.45) / glow.size)
    bright = float(np.count_nonzero(glow > 0.45) / glow.size)

    return {
        "nodes": int(v.shape[0]),
        "defects": defects,
        "defects_pos": left,
        "defects_neg": right,
        "mean_glow": float(glow.mean()),
        "coh_locked_frac": coh_locked,
        "bright_frac": bright,
        "locked_frac": coh_locked,   # alias: keep the old name meaningful
        "mean_radius": float(radius.mean()),
    }'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: telemetry()")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("patched; py_compile OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    sys.exit(1)

for i, line in enumerate(open(PATH, encoding="utf-8").read().splitlines(), 1):
    if "locked" in line or "bright" in line:
        print(f"  {i}: {line.strip()[:80]}")
