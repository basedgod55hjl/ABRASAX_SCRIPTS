"""Why does brain3d report 4.6% locked while the renderer reports 92.6%?

MEASURED
    :9700/telemetry.json          locked_frac = 0.926270
    brain3d.telemetry(verts)      locked_frac = 0.046

Both derive from the same 4096-node field. A 20x disagreement means one of the two
is computing something different from what it claims, and my own doc says "if the
picture and the numbers could disagree, one of them would be lying". So find out
which.

The two formulas:

  renderer  fb_phase_lock:  coh = 0.5 + 0.5*cos(2*pi*ln(1+r2)*PHI)
                            locked = coh >= FB_COH_FLOOR*0.85   (0.85*0.999999)
                            locked_frac = count(locked)/n

  brain3d   glow = base * coh * breath,  where base is the FIELD value
            locked_frac = count(glow > 0.45)/n

These are different quantities:
  * the renderer tests the coherence term alone
  * brain3d tests base * coh * breath, which is multiplied by the field activation

If the field is dim, glow is small even when coherence is perfect, so brain3d's
"locked" collapses. The renderer's number is the one that matches the shader's
actual gate.

This measures both, plus the intermediate distributions, so the difference is
attributed rather than guessed.
"""
import math
import sys

import numpy as np

sys.path.insert(0, r"C:\ABRASAX\ENGINE\floating_brain")

from brain3d import PHI, PHI_INV, DIM_IN, DIM_PROJ, NODES, FIELD_W, load_field

field = load_field()
print(f"field: {field.size} values, min={field.min():.4f} mean={field.mean():.4f} "
      f"max={field.max():.4f}")

print("\n=== recompute both notions of 'locked' ===")

coh_hits = 0
glow_hits = 0
cohs = []
glows = []
bases = []

for i in range(NODES):
    px, py = i % FIELD_W, i // FIELD_W
    base = float(field[py * FIELD_W + px])
    bases.append(base)

    vec = np.empty(DIM_IN, dtype=np.float32)
    for d in range(DIM_IN):
        ww = PHI_INV ** (d % 8)
        vec[d] = base * ww * math.sin((px * (d + 1) + py * (d + 3)) * 0.017)
    norm = float(np.sqrt(np.dot(vec, vec)))
    denom = 1.0 + norm + PHI_INV + 0.5
    folded = 0.0
    w = 1.0
    for d in range(DIM_PROJ, DIM_IN):
        folded += vec[d] * w
        w *= PHI_INV
    fterm = folded * PHI_INV * PHI_INV
    acc = np.array([(vec[k] + fterm) / denom for k in range(DIM_PROJ)], dtype=np.float32)
    r2 = float(np.dot(acc, acc))

    phase = 2.0 * math.pi * math.log(1.0 + r2) * PHI
    coh = 0.5 + 0.5 * math.cos(phase)
    cohs.append(coh)

    breath = 0.5 + 0.5 * math.sin(2.0 * math.pi * 7.83 * 0.0 * (1.0 + r2 * PHI_INV))
    glow = base * coh * breath
    glows.append(glow)

    # the renderer's gate: coherence alone, above 0.85 * floor
    if coh >= 0.999999 * 0.85:
        coh_hits += 1
    # brain3d's gate: the product, above 0.45
    if glow > 0.45:
        glow_hits += 1

bases = np.array(bases)
cohs = np.array(cohs)
glows = np.array(glows)

print(f"  base (field) : mean={bases.mean():.4f}  min={bases.min():.4f}  "
      f"max={bases.max():.4f}")
print(f"  coherence    : mean={cohs.mean():.4f}  min={cohs.min():.4f}  "
      f"max={cohs.max():.4f}")
print(f"  glow product : mean={glows.mean():.4f}  min={glows.min():.4f}  "
      f"max={glows.max():.4f}")
print()
print(f"  renderer notion (coh >= 0.85)   : {coh_hits}/{NODES} = "
      f"{coh_hits / NODES * 100:.2f}%")
print(f"  brain3d notion  (glow > 0.45)   : {glow_hits}/{NODES} = "
      f"{glow_hits / NODES * 100:.2f}%")

print("\n=== attribution ===")
if coh_hits / NODES > 0.9 and glow_hits / NODES < 0.1:
    print("  CONFIRMED: the difference is the multiplication by the field activation.")
    print("  Coherence alone is high (" + f"{coh_hits / NODES * 100:.1f}%"
          + "), but base*coh*breath rarely exceeds 0.45 because base is small.")
    print("  So the two numbers answer different questions:")
    print("    renderer  'what fraction passes the shader's coherence gate'")
    print("    brain3d   'what fraction is visibly bright'")
    print("  brain3d's label 'locked' is therefore MISLEADING -- it should be")
    print("  reporting the coherence gate, or be renamed to something like")
    print("  'bright_frac'.")
    verdict = "brain3d label is wrong"
else:
    print("  the two notions are close; the difference needs another explanation")
    verdict = "unexplained"

print(f"\nVERDICT: {verdict}")
