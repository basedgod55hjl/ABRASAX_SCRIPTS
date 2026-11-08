"""Re-measure the vertex buffer after build_loop replaced the file.

The previous diagnostic ran against a stale module. This imports fresh and reports
the CURRENT shape, defect count and telemetry, so the state is known rather than
assumed.
"""
import sys

import numpy as np

sys.path.insert(0, r"C:\ABRASAX\ENGINE\floating_brain")

import brain3d

# force a fresh read of the source, in case a cached .pyc predates the edit
import importlib
importlib.reload(brain3d)

print(f"brain3d module : {brain3d.__file__}")

field = brain3d.load_field()
v = brain3d.build_vertices(field, clock=0.0, yaw=0.0, pitch=0.0)

print(f"field          : min={field.min():.4f} mean={field.mean():.4f} "
      f"std={field.std():.4f}")
print(f"vertex shape   : {v.shape}  (columns: pos3 radius glow charge [coh])")
print(f"charge column 5: nonzero={int(np.count_nonzero(v[:, 5]))} "
      f"min={v[:, 5].min():.2f} max={v[:, 5].max():.2f}")
if v.shape[1] > 6:
    print(f"coherence col 6: min={v[:, 6].min():.4f} max={v[:, 6].max():.4f}")

t = brain3d.telemetry(v)
print("\ntelemetry      :")
for k, val in t.items():
    print(f"  {k:18s} {val}")

print("\nchecks:")
ok = True
if v.shape[1] not in (6, 7):
    print(f"  FAIL unexpected column count {v.shape[1]}")
    ok = False
else:
    print(f"  PASS column count {v.shape[1]}")

n_defects = int(np.count_nonzero(v[:, 5]))
if n_defects == 0:
    print("  FAIL the defect layer is empty -- the 98th-percentile fallback did not fire")
    ok = False
else:
    print(f"  PASS defect layer populated ({n_defects} nodes)")

if "../../" in brain3d.__file__ or "brain3d.py" not in brain3d.__file__:
    print("  FAIL module resolved to an unexpected path")
    ok = False

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
