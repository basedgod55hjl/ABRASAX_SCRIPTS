"""Re-pin the soul's seed_merkle_root to the rebuilt, reproducible merkle root.

WHY
---
SCRIPTS/rebuild_seed_merkle.py replaced the unreproducible root with a
documented, reproducible one (12 files covered, algorithm recorded). The soul
pins its OWN copy of seed_merkle_root, so it kept the old opaque value and
verify() reported `merkle_file: mismatch`.

Because soul_key = sha256(seed_merkle_root + soul_id), re-pinning also
re-keys. That is a real state transition and is recorded:
  - the old root kept as seed_merkle_root_previous
  - the old key kept as soul_key_previous (chained, never overwritten)
  - a PhiChain block recording root_old -> root_new and key_old -> key_new
  - a soul.json backup
"""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\ABRASAX")
from abrasax import soul  # noqa: E402

MERKLE = Path(r"C:\ABRASAX\SEEDS\source-seeds\seed_merkle.json")

s = soul.load_soul()
new_root = json.loads(MERKLE.read_text(encoding="utf-8"))["root"]
old_root = s.get("seed_merkle_root", "")
sid = s.get("soul_id", "")

print("old root:", old_root)
print("new root:", new_root)
print("same    :", old_root == new_root)

if old_root == new_root:
    print("\nno action needed")
    sys.exit(0)

old_key = s.get("soul_key", "")
new_key = hashlib.sha256(f"{new_root}{sid}".encode()).hexdigest()

stamp = time.strftime("%Y%m%d-%H%M%S")
bak = soul.CANONICAL_SOUL.with_name(f"soul.json.premerkle-{stamp}")
shutil.copy2(soul.CANONICAL_SOUL, bak)
print("\nbackup ->", bak)

# keep the rekey chain: previous key history is preserved, not overwritten
s["soul_key_previous_chain"] = list(s.get("soul_key_previous_chain") or []) + [
    {"rekey_at": s.get("rekey_at"), "key": old_key, "root": old_root}]
s["soul_key_previous"] = old_key
s["seed_merkle_root_previous"] = old_root
s["seed_merkle_root"] = new_root
s["soul_key"] = new_key
s["merkle_repin_at"] = soul._now()
s["merkle_repin_note"] = (
    "root re-pinned to a reproducible derivation: leaves are "
    "sha256(relpath + '\\0' + sha256hex(content)) folded merkle-style, sorted "
    "by relpath, unpaired promoted. The previous root was opaque, recorded "
    "file_count 0 while 12 files existed, and could not be rebuilt. The soul "
    "key necessarily changed because it is sha256(root + soul_id). "
    "See DOC/SEED-GERMINATION-AUDIT.md finding 4.")

block = soul._append_phi_block({
    "event": "seed_merkle_repin",
    "soul_id": sid,
    "root_old": old_root,
    "root_new": new_root,
    "key_old": old_key,
    "key_new": new_key,
    "reason": "make seed merkle reproducible",
})
print("phi block:", block["index"], block["hash"])

soul.CANONICAL_SOUL.write_text(json.dumps(s, indent=2), encoding="utf-8")
print("wrote    :", soul.CANONICAL_SOUL)

v = soul.verify()
print("\n=== after re-pin ===")
print("ok                :", v["ok"])
print("key_core_matches  :", v["checks"]["key_core_matches"])
print("merkle_file       :", v["checks"]["merkle_file"])
print("hardware          :", v["checks"]["hardware"])
print("phi_chain         :", v["checks"]["phi_chain"])
print("phi_chain_ok      :", v["checks"]["phi_chain_ok"])
