"""Fix test_cbm_bridge.py: empty seed is REJECTED by design, not round-trippable.

Measured: abrasax/cbm.py:254 raises ValueError("seed empty"). My test asserted a
0-byte round trip, which is wrong -- and the implementation is right to refuse:
an empty seed silently encoding to a valid-looking DNA frame would let downstream
code treat "no seed" as "a seed".

So:
  * remove 0 from the round-trip parameter list
  * add an explicit test pinning the rejection as intentional behaviour
"""
import sys

PATH = r"C:\ABRASAX\TESTS\python\test_cbm_bridge.py"
src = open(PATH, encoding="utf-8").read()

if "test_empty_seed_is_rejected" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '@pytest.mark.parametrize("n", [0, 1, 2, 15, 16, 17, 255, 256, 511, 512, 513, 4096])'
NEW = '@pytest.mark.parametrize("n", [1, 2, 15, 16, 17, 255, 256, 511, 512, 513, 4096])'
if OLD not in src:
    print("ANCHOR-NOT-FOUND: parametrize list")
    sys.exit(1)
src = src.replace(OLD, NEW, 1)

ANCHOR = "def test_roundtrip_is_reported_by_helper():"
NEWTEST = '''def test_empty_seed_is_rejected_not_silently_accepted():
    """Measured: cbm.py:254 raises ValueError("seed empty").

    An empty seed encoding to a valid-looking DNA frame would be worse than an
    error, because downstream code would treat "no seed" as "a seed". This test
    pins the rejection as intentional rather than incidental.
    """
    with pytest.raises(ValueError):
        cbm_bridge.seed_to_cbm(b"")
    with pytest.raises(ValueError):
        cbm_bridge.seed_to_cbm(bytearray())


'''
if ANCHOR not in src:
    print("ANCHOR-NOT-FOUND: helper test")
    sys.exit(1)
src = src.replace(ANCHOR, NEWTEST + ANCHOR, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: 0 removed from round trip, rejection pinned")
