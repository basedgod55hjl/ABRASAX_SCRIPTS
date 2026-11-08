"""Do brain3d and the renderer now agree on the locked fraction?

Before the fix:  renderer 92.6%, brain3d 4.6% -- same field, 20x apart, both called
`locked_frac`.

After the fix, brain3d reports two numbers:
    coh_locked_frac   the coherence gate   (was mislabelled locked_frac)
    bright_frac       what is actually bright

The claim to test: `coh_locked_frac` should track the renderer's `locked_frac`, and
`bright_frac` should track the 4.6% figure. If coh_locked_frac still sits near 4.6%,
the fix did not change the computation -- only the name -- and that must be stated.
"""
import json
import sys
import urllib.request

sys.path.insert(0, r"C:\ABRASAX\ENGINE\floating_brain")

from brain3d import build_vertices, load_field, telemetry

# the renderer's own number, straight from the wire
try:
    with urllib.request.urlopen("http://127.0.0.1:9700/telemetry.json?clock=0",
                                timeout=10) as r:
        render_tel = json.loads(r.read().decode())
except Exception as e:  # noqa: BLE001
    render_tel = {}
    print(f"renderer unreachable: {type(e).__name__}: {e}")

v = build_vertices(load_field(), clock=0.0, yaw=0.0, pitch=0.0)
t = telemetry(v)

print("=== both sides ===")
print(f"  renderer locked_frac   : {render_tel.get('locked_frac')}")
print(f"  brain3d  coh_locked_frac: {t['coh_locked_frac']:.4f}")
print(f"  brain3d  bright_frac    : {t['bright_frac']:.4f}")
print(f"  brain3d  locked_frac    : {t['locked_frac']:.4f}  (alias of coh_locked_frac)")
print(f"  brain3d  mean_glow      : {t['mean_glow']:.4f}")
print(f"  renderer mean_glow      : {render_tel.get('mean_glow')}")
print(f"  brain3d  defects        : {t['defects']}  (+{t['defects_pos']}/-{t['defects_neg']})")
print(f"  renderer defects        : "
      f"{(render_tel.get('defects_pos') or 0) + (render_tel.get('defects_neg') or 0)}")

print("\n=== verdict ===")
rl = render_tel.get("locked_frac")
if rl is None:
    print("  cannot compare: renderer telemetry unavailable")
    sys.exit(0)

delta = abs(t["coh_locked_frac"] - rl)
print(f"  |brain3d.coh_locked - renderer.locked| = {delta:.4f}")
if delta < 0.10:
    print("  AGREEMENT: the two now measure the same thing.")
elif delta < 0.30:
    print("  PARTIAL: same order, different gate constant. Acceptable but worth")
    print("  noting -- the two use different thresholds on the same quantity.")
else:
    print("  STILL DIVERGENT: renaming did not change the computation. brain3d's")
    print("  glow buffer does not carry raw coherence (it is base*coh*breath), so")
    print("  no threshold on it can reproduce the renderer's gate. The honest fix")
    print("  is to store coherence separately in the vertex buffer.") 

# and the bright fraction should match the old 4.6%
print(f"\n  bright_frac {t['bright_frac']:.4f} vs the old figure 0.0457 -> "
      f"{'matches' if abs(t['bright_frac'] - 0.0457) < 0.02 else 'differs'}")
