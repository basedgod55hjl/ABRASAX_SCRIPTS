"""Verify a committed TON anchor snapshot with no network at all.

Why this exists separately from `ton_offload.py verify`: that command re-hashes
the *live* evidence files, so it only works on the machine that made the anchor.
This one checks a snapshot in isolation -- record self-hash, Merkle root from the
recorded leaf hashes, and every per-file audit path -- which is what a third
party (or CI) can do with the repository alone. Optionally, with --onchain, it
also compares the recorded block hash against a live indexer.

Usage:
    python SCRIPTS/automation/ton_anchor_check.py              # every snapshot
    python SCRIPTS/automation/ton_anchor_check.py <file.json>
    python SCRIPTS/automation/ton_anchor_check.py --onchain
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
import urllib.request

DOCS = os.path.join(r"C:\abrasax", "DOC", "ton-anchors")
BLOCK_URLS = {
    "tonapi": "https://tonapi.io/v2/blockchain/blocks/(-1,8000000000000000,{seqno})",
    "toncenter_v2": ("https://toncenter.com/api/v2/getBlockHeader?"
                     "workchain=-1&shard=-9223372036854775808&seqno={seqno}"),
}


def sha_pair(a: str, b: str) -> str:
    return hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()


def merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return "0" * 64
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [sha_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def fold(leaf: str, path: list[dict]) -> str:
    cur = leaf
    for step in path:
        cur = (sha_pair(cur, step["hash"]) if step["side"] == "right"
               else sha_pair(step["hash"], cur))
    return cur


def record_hash(rec: dict) -> str:
    body = json.dumps({k: rec[k] for k in ("merkle_root", "leaf_count", "ton",
                                           "kind")}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def normalise(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) == 64 and all(c in "0123456789abcdefABCDEF" for c in text):
        return text.lower()
    try:
        import base64
        raw = base64.b64decode(text, validate=True)
    except Exception:  # noqa: BLE001
        return None
    return raw.hex() if len(raw) == 32 else None


def onchain(seqno: int, want_root: str, attempts: int = 3):
    """Per provider: (verdict, line) where verdict is True/False/None.

    None means the provider did not answer -- that is an availability fact, and
    it must not be dressed up as a hash mismatch.
    """
    out = []
    for name, tpl in BLOCK_URLS.items():
        doc = None
        last = ""
        for attempt in range(1, attempts + 1):
            try:
                req = urllib.request.Request(
                    tpl.format(seqno=seqno),
                    headers={"User-Agent": "abrasax-anchor-check/1"})
                with urllib.request.urlopen(req, timeout=25) as resp:
                    doc = json.loads(resp.read().decode("utf-8", "replace"))
                break
            except Exception as exc:  # noqa: BLE001
                last = "%s: %s" % (type(exc).__name__, exc)
                if attempt < attempts:
                    import time
                    time.sleep(0.8 * attempt)
        if doc is None:
            out.append((None, "%s: no answer after %d attempts (%s)"
                        % (name, attempts, last)))
            continue
        box = doc.get("result") if isinstance(doc.get("result"), dict) else doc
        root = normalise(box.get("root_hash") or (box.get("id") or {}).get("root_hash"))
        gen = box.get("gen_utime")
        out.append((root == want_root,
                    "%s: root %s, gen_utime %s"
                    % (name, "matches" if root == want_root else "DIFFERS", gen)))
    return out


def check(path: str, check_chain: bool) -> bool:
    rec = json.load(open(path, encoding="utf-8"))
    name = os.path.basename(path)
    ok = True

    if record_hash(rec) != rec.get("record_sha256"):
        print("  FAIL record_sha256 does not re-derive")
        ok = False

    leaves = [f["sha256"] for f in rec["files"]]
    if merkle_root(leaves) != rec["merkle_root"]:
        print("  FAIL merkle root does not re-derive from %d leaves" % len(leaves))
        ok = False

    bad_proofs = []
    for rel, path_steps in rec["proofs"].items():
        leaf = next((f["sha256"] for f in rec["files"] if f["path"] == rel), None)
        if leaf is None or fold(leaf, path_steps) != rec["merkle_root"]:
            bad_proofs.append(rel)
    if bad_proofs:
        print("  FAIL proofs do not fold: %s" % ", ".join(bad_proofs))
        ok = False

    ton = rec.get("ton", {})
    seqno = ton.get("masterchain_seqno")
    blk = ton.get("anchored_block") or {}
    print("  seqno=%s leaves=%d proofs=%d block=%s"
          % (seqno, len(leaves), len(rec["proofs"]),
             (blk.get("root_hash") or "-")[:12]))
    if check_chain and seqno and blk.get("root_hash"):
        verdicts = onchain(int(seqno), blk["root_hash"])
        answered = [v for v, _ in verdicts if v is not None]
        for verdict, line in verdicts:
            tag = "PASS" if verdict else ("FAIL" if verdict is False else "NOTE")
            print("  %s %s" % (tag, line))
        if not answered:
            print("  FAIL no indexer answered; the block hash is unverified")
            ok = False
        elif not all(answered):
            print("  FAIL an indexer answered with a different root hash")
            ok = False
        elif len(answered) == 1:
            print("  NOTE one indexer answered; hash matches, second opinion "
                  "unavailable (availability, not disagreement)")

    print("  %s %s" % ("PASS" if ok else "FAIL", name))
    return ok


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_chain = "--onchain" in sys.argv
    paths = args or sorted(glob.glob(os.path.join(DOCS, "anchor-*.json")))
    if not paths:
        print("no snapshots found in %s" % DOCS)
        return 1
    results = [check(p, check_chain) for p in paths]
    print("\n%d/%d snapshots verified%s"
          % (sum(results), len(results), " (with on-chain comparison)" if check_chain else ""))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
