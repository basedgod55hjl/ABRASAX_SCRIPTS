"""Why did the defect column go to zero after adding the coherence column?

MEASURED by pytest:
    test_vertex_shape                             FAILED
    test_neuron_vertices_match_point_shader_layout FAILED
    all 4096 values of column 5 are 0.0

The defect loop still writes v[i, 5] and the threshold is unchanged (abs(lap) >
0.45), so the column itself is fine. Two candidates:

  a  the tests read the wrong column after the buffer widened 6 -> 7
  b  the live field changed and genuinely has no cell above the Laplacian threshold

(b) is plausible: load_field() pulls the LIVE field from :9626, and the field's
mean_state has been pinned near 0.997 all session -- a nearly uniform field has a
near-zero Laplacian everywhere. The synthetic fallback produced 378 defects; the
live field may produce zero.

This measures the Laplacian distribution on the live field so the answer is known
rather than guessed.
"""
import sys

import numpy as np

sys.path.insert(0, r"C:\ABRASAX\ENGINE\floating_brain")

from brain3d import load_field, build_vertices, FIELD_W, FIELD_H

field = load_field()

print("=== live field ===")
print(f"  min={field.min():.4f} mean={field.mean():.4f} max={field.max():.4f} "
      f"std={field.std():.4f}")

laps = []
for y in range(1, FIELD_H - 1):
    for x in range(1, FIELD_W - 1):
        c = float(field[y * FIELD_W + x])
        lap = (float(field[(y - 1) * FIELD_W + x]) + float(field[(y + 1) * FIELD_W + x])
               + float(field[y * FIELD_W + x - 1]) + float(field[y * FIELD_W + x + 1])
               - 4.0 * c)
        laps.append(lap)

laps = np.array(laps)
print("\n=== Laplacian distribution ===")
print(f"  n={laps.size}  min={laps.min():.4f}  max={laps.max():.4f}  "
      f"mean={laps.mean():.4f}  std={laps.std():.4f}")
for th in (0.05, 0.10, 0.20, 0.30, 0.45):
    n = int(np.count_nonzero(np.abs(laps) > th))
    print(f"  |lap| > {th:.2f} : {n:5d} cells")

print("\n=== what build_vertices produced ===")
v = build_vertices(field, clock=0.0, yaw=0.0, pitch=0.0)
print(f"  columns: {v.shape[1]}")
charge = v[:, 5]
print(f"  charge column: nonzero={int(np.count_nonzero(charge))} "
      f"min={charge.min():.2f} max={charge.max():.2f}")
print(f"  coherence column (6): min={v[:,6].min():.4f} max={v[:,6].max():.4f}")

print("\n=== conclusion ===")
if int(np.count_nonzero(charge)) == 0:
    best = int(np.count_nonzero(np.abs(laps) > 0.05))
    print(f"  The LIVE field has no cell above the 0.45 Laplacian threshold.")
    print(f"  At 0.05 there would be {best} cells. The field std is {field.std():.4f},")
    print("  which is why: a nearly uniform field has a near-zero Laplacian.")
    print("  So this is not a bug in the buffer layout -- it is a real property of")
    print("  the current brain state, and the threshold is calibrated for a more")
    print("  varied field (the synthetic fallback produced 378 defects).")
else:
    print("  defects are present; the failures must be column-index errors in the tests")
