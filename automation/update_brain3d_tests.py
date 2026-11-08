"""Update test_brain3d.py for the 7-column layout.

The vertex buffer gained a coherence column so brain3d's locked fraction could match
the renderer's coherence gate. The tests still assert the old 6-column shape:

    assert verts.shape == (4096, 6)   ->   AssertionError: expected (4096,6), got (4096,7)

That is the test being out of date, not the code being wrong. The fix also ADDS a
test that the new column is actually meaningful, so the widening cannot quietly
become decoration:

    column 6 must be in [0,1], must vary, and coh_locked_frac must be computed from
    it rather than from the glow proxy.
"""
import shutil
import sys
import time

PATH = r"C:\ABRASAX\TESTS\python\test_brain3d.py"
src = open(PATH, encoding="utf-8").read()

if "COLUMNS = 7" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''def test_vertex_shape(verts):
    assert verts.shape == (4096, 6), f"expected (4096,6), got {verts.shape}"
    assert verts.dtype == np.float32'''

NEW = '''COLUMNS = 7          # pos(3) radius glow charge coherence


def test_vertex_shape(verts):
    assert verts.shape == (4096, COLUMNS), f"expected (4096,{COLUMNS}), got {verts.shape}"
    assert verts.dtype == np.float32


def test_coherence_column_is_meaningful(verts):
    """Column 6 must carry real coherence, not a constant or a copy of glow.

    This column exists because glow = base*coherence*breath and cannot be
    un-multiplied. If the column were ever filled with something else -- or with
    glow again -- the locked fraction would silently drift away from the
    renderer's. Pin the property, not the implementation.
    """
    coh = verts[:, 6]
    assert coh.min() >= 0.0 and coh.max() <= 1.0, f"coherence out of range [{coh.min()}, {coh.max()}]"
    assert coh.std() > 1e-3, "coherence column is constant -- it is not being computed"
    # it must differ from the glow column, or the widening bought nothing
    assert not np.allclose(coh, verts[:, 4]), (
        "coherence column equals glow -- it is not the un-multiplied value")


def test_locked_fraction_uses_the_coherence_column(verts):
    """coh_locked_frac must be the coherence gate, not the brightness proxy."""
    from brain3d import telemetry
    t = telemetry(verts)
    expected = float(np.count_nonzero(verts[:, 6] >= 0.85) / verts.shape[0])
    assert t["coh_locked_frac"] == pytest.approx(expected, abs=1e-9), (
        f"coh_locked_frac {t['coh_locked_frac']} != gate on column 6 ({expected})")
    # and it must differ from bright_frac, which answers a different question
    assert t["coh_locked_frac"] != pytest.approx(t["bright_frac"], abs=1e-6), (
        "locked and bright are the same number again -- the labels have collapsed")'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: test_vertex_shape")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)

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
