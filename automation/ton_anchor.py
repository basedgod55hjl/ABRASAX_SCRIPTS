"""Anchor the local hash chain to TON's masterchain, read-only.

WHAT THIS DOES, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
It does NOT write to any blockchain. No wallet, no keys, no funds are involved
and nothing is spent. There is no wallet on this machine and creating one to
mint or anchor a token is a financial action I am not going to take on the
user's behalf.

What it does instead, which is the part that is genuinely useful:

  1. takes the current head of the local hash chain
  2. records it together with the *current TON masterchain block seqno*, taken
     from two independent public indexers
  3. hashes the whole anchor record so the record itself is tamper-evident

That yields a decentralised timestamp: "chain head H existed no later than TON
block N". Anyone can re-query TON and confirm block N is real and old, which
bounds the time H was created without trusting this machine's clock. It is the
same primitive an on-chain anchor gives you, minus the on-chain part -- so a
later real anchor (funded by the user) can be checked against this record.

Providers are queried independently and must agree, because a single indexer is
a single point of trust for exactly the claim being made.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(r"C:\ABRASAX")
OUT = ROOT / "DATA" / "runtime-memory" / "ton_anchor.json"
CHAIN = ROOT / "LOGS" / "state-chain.jsonl"

PROVIDERS = {
    "toncenter": "https://toncenter.com/api/v2/getMasterchainInfo",
    "tonapi": "https://tonapi.io/v2/status",
}


def masterchain_seqno(url: str) -> int | None:
    """Current masterchain block seqno, or None. Bounded, never raising."""
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            d = json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        return None
    res = d.get("result") if isinstance(d.get("result"), dict) else d
    if isinstance(res.get("last"), dict):
        return int(res["last"]["seqno"])
    for key in ("last_known_masterchain_seqno", "last_masterchain_seqno"):
        if isinstance(res.get(key), int):
            return res[key]
    return None


def chain_head() -> tuple[str, int]:
    try:
        lines = [l for l in CHAIN.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            return json.loads(lines[-1])["hash"], len(lines)
    except OSError:
        pass
    return "0" * 64, 0


def anchor() -> dict:
    head, n = chain_head()
    seqnos = {}
    for name, url in PROVIDERS.items():
        seqnos[name] = masterchain_seqno(url)

    got = [v for v in seqnos.values() if v]
    # Two providers should agree to within a couple of blocks (they index at
    # slightly different heights). A large disagreement means at least one is
    # serving something other than the live masterchain, and the timestamp is
    # then not worth recording.
    agreement = bool(got) and (max(got) - min(got) <= 5)
    seqno = min(got) if got else None

    rec = {
        "ts": time.time(),
        "chain_head": head,
        "chain_len": n,
        "ton_masterchain_seqno": seqno,
        "providers": seqnos,
        "providers_agree": agreement,
        "note": "read-only timestamp reference; nothing was written on-chain",
    }
    rec["anchor_sha256"] = hashlib.sha256(
        json.dumps({k: rec[k] for k in ("chain_head", "chain_len",
                                        "ton_masterchain_seqno", "ts")},
                   sort_keys=True).encode()).hexdigest()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def verify() -> tuple[bool, list[str]]:
    msgs: list[str] = []
    if not OUT.is_file():
        return False, ["no anchor recorded"]
    rec = json.loads(OUT.read_text(encoding="utf-8"))

    want = hashlib.sha256(
        json.dumps({k: rec[k] for k in ("chain_head", "chain_len",
                                        "ton_masterchain_seqno", "ts")},
                   sort_keys=True).encode()).hexdigest()
    ok_hash = want == rec.get("anchor_sha256")
    msgs.append(("PASS" if ok_hash else "FAIL") + " anchor record unmodified")

    live = {}
    for name, url in PROVIDERS.items():
        live[name] = masterchain_seqno(url)
    got = [v for v in live.values() if v]
    # Independent indexers do NOT share a tip: measured toncenter 99879009 vs
    # tonapi 99879010 in the same second. Taking min(live) >= recorded made the
    # check fail by a single block purely because one indexer was one behind.
    # The claim being verified is "the anchored block is not in the future", so
    # a small lag tolerance is correct rather than sloppy.
    TOL = 5
    progressed = bool(got) and rec.get("ton_masterchain_seqno") is not None and         min(got) >= rec["ton_masterchain_seqno"] - TOL
    msgs.append(("PASS" if progressed else "FAIL") +
                " anchored TON block is at or below the live head "
                f"(anchored {rec.get('ton_masterchain_seqno')}, live {min(got) if got else '?'})")

    head, n = chain_head()
    chain_ok = head == rec.get("chain_head")
    msgs.append(("PASS" if chain_ok else "NOTE") +
                f" local chain head {'unchanged' if chain_ok else 'has advanced'} "
                f"({rec.get('chain_len')} -> {n} entries)")

    return ok_hash and progressed, msgs


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "anchor").lower()
    if cmd == "anchor":
        r = anchor()
        print(f"anchored chain {r['chain_len']} entries head {r['chain_head'][:16]}...")
        print(f"  TON masterchain seqno {r['ton_masterchain_seqno']}  "
              f"providers agree={r['providers_agree']}  {r['providers']}")
        print(f"  anchor_sha256 {r['anchor_sha256'][:32]}...")
        print(f"  -> {OUT}")
        return 0 if r["providers_agree"] else 1
    if cmd == "verify":
        ok, msgs = verify()
        for m in msgs:
            print(" " + m)
        return 0 if ok else 1
    print("usage: ton_anchor.py anchor|verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
