"""Repair 1: commit the FULL soul key, with an auditable transition record.

Before:  ok = key[:16] == sha256(seed_merkle_root + soul_id)[:16]
         -> 64 of 256 bits checked; remaining 192 bits unconstrained.
         A forged key (correct prefix + 48 zeros) passed verify().

After:   ok = key == sha256(seed_merkle_root + soul_id)
         -> full 256-bit commitment.

The existing soul_key does NOT equal the digest, so re-keying is a real state
transition. It is recorded:
  - previous key preserved as soul_key_previous (never deleted)
  - rekey_at + rekey_note recorded
  - a PhiChain block appended, so the transition is in the tamper-evident chain
  - a soul.json backup taken first

This script is idempotent: if the key already equals the core it does nothing.
"""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\ABRASAX")
from abrasax import soul  # noqa: E402

s = soul.load_soul()
root = s.get("seed_merkle_root", "")
sid = s.get("soul_id", "")
core = hashlib.sha256(f"{root}{sid}".encode()).hexdigest()
current = str(s.get("soul_key", "")).lower()

print("soul_id      :", sid)
print("core digest  :", core)
print("current key  :", current)
print("already committed:", current == core)

if current == core:
    print("\nno action needed")
    sys.exit(0)

# --- back up, then re-key with a transition record -------------------------
stamp = time.strftime("%Y%m%d-%H%M%S")
bak = soul.CANONICAL_SOUL.with_name(f"soul.json.precommit-{stamp}")
shutil.copy2(soul.CANONICAL_SOUL, bak)
print("\nbackup ->", bak)

s["soul_key_previous"] = current
s["soul_key"] = core
s["rekey_at"] = soul._now()
s["rekey_note"] = (
    "full-key commitment: soul_key now equals sha256(seed_merkle_root+soul_id). "
    "Previous value was only prefix-compatible (16/64 hex chars), with 192 "
    "unconstrained bits; a forged key with 48 zero tail chars passed verify(). "
    "See DOC/SEED-GERMINATION-AUDIT.md finding 1.")

block = soul._append_phi_block({
    "event": "soul_rekey_full_commitment",
    "soul_id": sid,
    "key_previous_prefix": current[:16],
    "key_previous_full": current,
    "key_new": core,
    "reason": "close 16-hex-char prefix weakness",
})
print("phi block    :", block["index"], block["hash"])

soul.CANONICAL_SOUL.write_text(json.dumps(s, indent=2), encoding="utf-8")
print("wrote        :", soul.CANONICAL_SOUL)

v = soul.verify()
print("\n=== after re-key ===")
print("ok                :", v["ok"])
print("key_core_matches  :", v["checks"]["key_core_matches"])
print("phi_chain         :", v["checks"]["phi_chain"])
print("phi_chain_ok      :", v["checks"]["phi_chain_ok"])
