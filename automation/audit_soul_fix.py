"""Did the soul.py fix actually make verify() honest, or just make the test green?

The working tree has an uncommitted change to abrasax/soul.py made by a background
process (build_loop). Two edits:

  BEFORE  ok = core.startswith(key[:16]) or key.startswith(core[:16])
  AFTER   ok = key[:16] == core[:16]

  BEFORE  return {"ok": bool(soul_id) and chain_ok is not False, ...}
  AFTER   return {"ok": ... and ok is True, ...}

The second is the important one: `ok` previously ignored the key check entirely, so a
soul with a fabricated soul_key still reported ok=True -- exactly what the xfail
test_soul.py::test_canonical_soul_key_matches_documented_derivation described.

A change that turns a red test green is not automatically correct. This proves the
new behaviour on four inputs:

  1  the real on-disk soul          -> what does verify() now say?
  2  a soul with a fabricated key   -> must be ok=False
  3  a soul with the correct key    -> must be ok=True
  4  a soul with no key at all      -> must not crash

If (2) still returns ok=True, the fix is cosmetic and must be rejected.
"""
import copy
import sys

sys.path.insert(0, r"C:\ABRASAX")

from abrasax import soul as S

ok_all = True


def report(name, passed, detail=""):
    global ok_all
    print(f"[{'PASS' if passed else 'FAIL'}] {name}"
          + (f" -- {detail}" if detail else ""))
    if not passed:
        ok_all = False


real = S.load_soul()
core = S._soul_key_core(real)
key = str(real.get("soul_key", "")).lower().replace("-", "")

print("=== 1. the real soul on disk ===")
print(f"  soul_id      : {real.get('soul_id')}")
print(f"  stored key   : {key[:24]}...")
print(f"  derived core : {core[:24]}...")
print(f"  prefix match : {key[:16] == core[:16]}")

v = S.verify(real)
print(f"  verify().ok  : {v.get('ok')}")
print(f"  key_core_matches: {v['checks'].get('key_core_matches')}")

print()
print("=== 2. fabricated key must be REFUSED ===")
bad = copy.deepcopy(real)
bad["soul_key"] = "deadbeefdeadbeefdeadbeefdeadbeef"
vb = S.verify(bad)
print(f"  verify().ok  : {vb.get('ok')}")
print(f"  key_core_matches: {vb['checks'].get('key_core_matches')}")
report("a fabricated soul_key is refused", vb.get("ok") is False,
       f"ok={vb.get('ok')}")

print()
print("=== 3. correct key must be ACCEPTED ===")
good = copy.deepcopy(real)
good["soul_key"] = core
vg = S.verify(good)
print(f"  verify().ok  : {vg.get('ok')}")
print(f"  key_core_matches: {vg['checks'].get('key_core_matches')}")
report("a correct soul_key is accepted", vg.get("ok") is True,
       f"ok={vg.get('ok')}")

print()
print("=== 4. no key at all must not crash ===")
none = copy.deepcopy(real)
none["soul_key"] = ""
try:
    vn = S.verify(none)
    print(f"  verify().ok  : {vn.get('ok')}")
    report("missing key handled without raising", True)
except Exception as e:  # noqa: BLE001
    print(f"  raised {type(e).__name__}: {e}")
    report("missing key handled without raising", False, str(e)[:60])

print()
print("=== 5. does the REAL soul pass the stricter gate? ===")
print(f"  real soul verify().ok = {v.get('ok')}")
if v.get("ok") is not True:
    print("  -> the on-disk soul no longer verifies. That is the honest consequence")
    print("     of a correct check: the stored key was never the derived digest.")
else:
    print("  -> the on-disk soul verifies under the stricter rule.")

print()
print("RESULT:", "PASS -- the fix makes verify() honest, not just green"
      if ok_all else "FAIL -- the change is cosmetic")
sys.exit(0 if ok_all else 1)
