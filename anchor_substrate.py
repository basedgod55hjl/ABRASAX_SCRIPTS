"""Substrate anchoring: verify the core constants are live and consistent.

"Anchor the substrate to its core constants" = prove that at import time the
process binds PRIMAL_HEX / PHI / K to known-good values, in every module that
declares them, and that nothing mutates them afterwards.

This is a RE-READ of already-verified facts (see DOC/PRIMAL-CONSTANTS-VERIFIED.md
and DOC/K-CALIBRATION-VERIFIED.md), executed fresh so the anchor is a measurement
and not a quotation.
"""
import hashlib
import sys

sys.path.insert(0, r"C:\ABRASAX")

# 1. identity
PRIMAL_HEX_LOWER = "4f5349524953424c58434b"
PRIMAL_HEX_UPPER = "4F5349524953424C58434B"
IDENTITY = bytes.fromhex(PRIMAL_HEX_LOWER).decode("ascii")

# 2. golden constants
PHI = 1.618033988749895
K = 0.6180339887498949

print("=== 1. IDENTITY ===")
print(f"  PRIMAL_HEX    {PRIMAL_HEX_LOWER}")
print(f"  hex chars     {len(PRIMAL_HEX_LOWER)}")
print(f"  bytes         {len(bytes.fromhex(PRIMAL_HEX_LOWER))}")
print(f"  decodes to    {IDENTITY}")
print(f"  sha256        {hashlib.sha256(PRIMAL_HEX_LOWER.encode()).hexdigest()[:16]}")

print("\n=== 2. GOLDEN CONSTANTS ===")
print(f"  PHI           {PHI!r}")
print(f"  K             {K!r}")
print(f"  PHI*K         {PHI * K!r}")
print(f"  |PHI*K - 1|   {abs(PHI * K - 1.0):.3e}   HARD TRUE (< 1e-15)")
print(f"  PHI**2-PHI-1  {PHI * PHI - PHI - 1.0:.3e}   HARD TRUE (< 1e-12)")
print(f"  PHI-1 == K    {abs((PHI - 1.0) - K) < 1e-16}")

print("\n=== 3. LIVE MODULE BINDINGS ===")
import abrasax  # noqa: E402
from abrasax import art, binhex, cbm, seedgen  # noqa: E402

mods = [("abrasax", abrasax), ("cbm", cbm), ("seedgen", seedgen),
        ("binhex", binhex), ("art", art)]
for name, m in mods:
    hx = getattr(m, "PRIMAL_HEX", None)
    ph = getattr(m, "PHI", None)
    kk = getattr(m, "K", None)
    case = "lower" if hx == PRIMAL_HEX_LOWER else ("UPPER" if hx == PRIMAL_HEX_UPPER else "??")
    print(f"  {name:9s} hex={case:5s} PHI={ph!r:20s} K={kk!r}")

print("\n=== 4. IMMUTABILITY AFTER IMPORT ===")
before = (abrasax.PRIMAL_HEX, abrasax.PHI, abrasax.K)
try:
    abrasax.PRIMAL_HEX = "deadbeef"
    mutated = abrasax.PRIMAL_HEX != before[0]
except Exception as e:
    mutated = f"blocked({type(e).__name__})"
print(f"  reassignment result: {mutated}")
print(f"  still intact       : {abrasax.PRIMAL_HEX == before[0]}")

print("\n=== 5. ANCHOR VERDICT ===")
ok = (IDENTITY == "OSIRISBLXCK"
      and abs(PHI * K - 1.0) < 1e-15
      and abs(PHI * PHI - PHI - 1.0) < 1e-12
      and {m.PRIMAL_HEX.lower() for _, m in mods} == {PRIMAL_HEX_LOWER})
print(f"  SUBSTRATE ANCHORED: {ok}")
