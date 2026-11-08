"""Align test_brain3d.py with the final design.

FINAL DESIGN (settled after three iterations that overwrote each other)

    build_vertices() returns a GPU buffer of exactly VSTRIDE=6 columns:
        pos(3) radius glow charge
    Coherence is computed internally and published as brain3d.last_coherence, NOT as
    a 7th column -- because the shader declares locations 0..3 with a 6-float stride,
    so a 7-column buffer would misread every vertex after the first.

    telemetry(v) therefore reports:
        coh_locked_frac   gate on last_coherence at 0.85 (the renderer's constant)
        bright_frac       fraction whose glow exceeds 0.45
        coherence_source  "side-channel" | "column6" | "glow-proxy"

The earlier test asserted (4096,7) and read column 6. Both are wrong under the final
design. This rewrites those tests to assert what is actually true, including that the
GPU buffer stays 6 wide -- which is the property that protects the renderer.
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\TESTS\python\test_brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "GPU_COLUMNS" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# replace the whole block of tests that were written for the 7-column design
start = src.find("COLUMNS = 7")
if start == -1:
    start = src.find("def test_vertex_shape(verts):")
if start == -1:
    print("ANCHOR-NOT-FOUND: test block")
    sys.exit(1)

end = src.find("def test_vertex_values_are_finite(verts):")
if end == -1:
    print("ANCHOR-NOT-FOUND: block end")
    sys.exit(1)

NEW = '''GPU_COLUMNS = 6     # pos(3) radius glow charge -- what the shader stride expects


def test_vertex_shape_is_the_gpu_stride(verts):
    """The exported buffer must match VSTRIDE.

    A 7th column here would misalign every vertex after the first: the shader
    declares locations 0..3 with a stride of VSTRIDE*4, so the extra column would
    be read as the next vertex's position. Garbage geometry that still renders.
    """
    import brain3d
    assert verts.shape == (4096, GPU_COLUMNS), (
        f"expected (4096,{GPU_COLUMNS}), got {verts.shape}")
    assert verts.shape[1] == brain3d.VSTRIDE, (
        f"buffer width {verts.shape[1]} != VSTRIDE {brain3d.VSTRIDE}")
    assert verts.dtype == np.float32


def test_coherence_is_published_separately(verts):
    """Coherence must exist as a side channel since it is not in the GPU buffer."""
    import brain3d
    coh = brain3d.last_coherence
    assert coh is not None, "build_vertices published no coherence vector"
    assert coh.shape == (4096,), f"coherence shape {coh.shape}"
    assert coh.min() >= 0.0 and coh.max() <= 1.0, (
        f"coherence out of range [{coh.min()}, {coh.max()}]")
    assert coh.std() > 1e-3, "coherence is constant -- it is not being computed"
    # it must differ from the glow column, or the side channel bought nothing
    assert not np.allclose(coh, verts[:, 4]), (
        "coherence equals glow -- it is not the un-multiplied value")


def test_locked_fraction_uses_coherence_not_glow(verts):
    """coh_locked_frac must be the coherence gate, and must say where it came from."""
    from brain3d import telemetry
    import brain3d
    t = telemetry(verts)
    assert t["coherence_source"] in ("side-channel", "column6"), (
        f"telemetry fell back to {t['coherence_source']}")
    expected = float(np.count_nonzero(brain3d.last_coherence >= 0.85) / 4096)
    assert t["coh_locked_frac"] == pytest.approx(expected, abs=1e-9), (
        f"coh_locked_frac {t['coh_locked_frac']} != gate on coherence ({expected})")


def test_locked_and_bright_are_different_questions(verts):
    """The two fractions must not collapse to the same number again."""
    from brain3d import telemetry
    t = telemetry(verts)
    assert abs(t["coh_locked_frac"] - t["bright_frac"]) > 1e-3, (
        "locked and bright are identical -- the labels have collapsed again")


'''

src = src[:start] + NEW + src[end:]

backup = PATH + ".bak-" + time.strftime("%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print(f"rewrote test block (backup {backup.rsplit(chr(92),1)[-1]})")

import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("py_compile: OK")
except py_compile.PyCompileError as e:
    print("STILL BROKEN:", e)
    sys.exit(1)
