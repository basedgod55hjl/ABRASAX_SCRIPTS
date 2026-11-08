"""Repair 3: make seed_merkle.json reproducible.

PROBLEM
-------
The shipped SEEDS/source-seeds/seed_merkle.json said:
    { "root": "fc41425b...b841da", "built_at": 1785897542.0263047, "file_count": 0 }
while 12 files sat beside it. Eight reconstruction attempts reproduced none of
it, and no generator exists in the repo. The root is load-bearing (the soul key
digest is sha256(seed_merkle_root + soul_id)) but could never be rebuilt if lost.

WHAT THIS DOES
--------------
Defines a canonical, documented derivation and applies it:

    leaf(file)  = sha256( bytes(  relpath + "\\0" + sha256hex(content)  ) )
    root        = merkle fold over leaves sorted by relpath
                  (odd tail: an unpaired leaf is promoted, not duplicated)
    file_count  = actual number of files covered

It records `algorithm` so a future reader knows exactly how to rebuild it, and
`previous_root` so the old opaque value is not lost.

Writes to the canonical path, keeping a backup. Idempotent: rerunning produces
the same root (built_at differs).
"""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

BASE = Path(r"C:\ABRASAX\SEEDS\source-seeds")
TARGET = BASE / "seed_merkle.json"
ALGO = "sha256(relpath + '\\0' + sha256hex(content)) leaves, merkle fold sorted by relpath, odd-promote"

# The merkle file describes the seed material. It must not hash itself, nor any
# backup it (or a previous run) produced -- otherwise every rebuild changes the
# file set, which changes the root, which makes the "reproducible" claim circular.
#: soul.json is a CONSUMER of the root, not seed material. It stores
#: seed_merkle_root, and soul_key = sha256(seed_merkle_root + soul_id), so
#: hashing it here creates a cycle:
#:     root = f(soul.json)   and   soul.json = g(root)
#: Measured 2026-10-18: mutating seed_merkle_root inside soul.json changed the
#: root from ddcc3161... to 24a5f451..., proving the dependency. No repin could
#: ever converge -- each write invalidated the root it had just been derived
#: from. Excluded so the merkle commits to the SEEDS only.
EXCLUDE_EXACT = {"seed_merkle.json", "soul.json"}
EXCLUDE_PREFIXES = ("seed_merkle.json.bak-", "soul.json.bak-", "soul.json.precommit-",
                    "soul.json.premerkle-")


def sha_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def leaf(rel: str, data: bytes) -> str:
    return sha_hex((rel + "\0" + sha_hex(data)).encode("utf-8"))


def merkle_fold(leaves: list[str]) -> str:
    if not leaves:
        return sha_hex(b"")
    layer = list(leaves)
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            if i + 1 < len(layer):
                nxt.append(sha_hex((layer[i] + layer[i + 1]).encode()))
            else:
                nxt.append(layer[i])          # promote unpaired
        layer = nxt
    return layer[0]


def build() -> dict:
    files = sorted(
        (p for p in BASE.rglob("*") if p.is_file()
         and p.name not in EXCLUDE_EXACT
         and not p.name.startswith(EXCLUDE_PREFIXES)),
        key=lambda p: p.relative_to(BASE).as_posix(),
    )
    entries = []
    for p in files:
        rel = p.relative_to(BASE).as_posix()
        data = p.read_bytes()
        entries.append({"path": rel, "sha256": sha_hex(data), "bytes": len(data),
                        "leaf": leaf(rel, data)})
    entries.sort(key=lambda e: e["path"])
    root = merkle_fold([e["leaf"] for e in entries])
    return {
        "algorithm": ALGO,
        "root": root,
        "file_count": len(entries),
        "built_at": time.time(),
        "files": entries,
    }


def main() -> int:
    previous = None
    if TARGET.exists():
        try:
            previous = json.loads(TARGET.read_text(encoding="utf-8"))
        except Exception:
            previous = None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        bak = TARGET.with_name(f"seed_merkle.json.bak-{stamp}")
        shutil.copy2(TARGET, bak)
        print("backup ->", bak)

    doc = build()
    if previous:
        doc["previous_root"] = previous.get("root")
        doc["previous_file_count"] = previous.get("file_count")
        doc["rebuilt_reason"] = (
            "old root was unreproducible and recorded file_count 0 while files "
            "existed; see DOC/SEED-GERMINATION-AUDIT.md finding 4")

    TARGET.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    print("files covered :", doc["file_count"])
    print("new root      :", doc["root"])
    print("previous root :", doc.get("previous_root"))
    print("root changed  :", doc.get("previous_root") != doc["root"])
    print("wrote         :", TARGET)

    # prove reproducibility: rebuild and compare
    again = build()
    print("reproducible  :", again["root"] == doc["root"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
