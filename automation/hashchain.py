"""Tamper-evident hash chain over ABRASAX state snapshots.

WHAT THIS IS
------------
An append-only chain where each entry commits to the previous entry's hash:

    hash_n = SHA256(prev_hash || canonical_json(payload_n))

Any edit to any historical payload breaks every hash after it, and the break is
located exactly. That is a real, testable integrity property.

WHAT THIS IS NOT
----------------
**Not a zero-knowledge proof.** A ZK proof proves a statement about *secret*
inputs without revealing them (e.g. "I know x such that H(x)=y" or "this
computation ran correctly") using a circuit, a witness, and a proving system
(Groth16/PLONK) that needs a trusted setup. This file does none of that. Calling
it zk would be false.

What it gives you instead: authenticity and ordering that anyone can verify from
the file alone, with no trust in us. If you want the actual ZK property
afterwards, the delta is:
    * a circuit describing the statement (circom or a Rust zkVM like risc0)
    * a proving key from a trusted setup (ptau ceremony file)
    * a verifier the other side runs
None of circom/snarkjs is installed here (node and cargo are), so that is a
separate build, not something to pretend at.

USAGE
    python hashchain.py append     # commit the current state
    python hashchain.py verify     # walk the chain, report the first break
    python hashchain.py head
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(r"C:\ABRASAX")
CHAIN = ROOT / "LOGS" / "state-chain.jsonl"
GENESIS = "0" * 64


def _read(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def snapshot() -> dict:
    """Compact state fingerprint. Deliberately small: this is a commitment, not
    a copy, so it proves what the system *said* without duplicating it."""
    s = _read(ROOT / "DATA" / "runtime-memory" / "s25_senses.json")
    m = _read(ROOT / "DATA" / "runtime-memory" / "s25_motion.json")
    c = _read(ROOT / "DATA" / "runtime-memory" / "cost.json")
    st = _read(ROOT / "LOGS" / "build-queue-state.json")
    b = s.get("battery") or {}
    sl = s.get("storage") or {}
    return {
        "phone_battery": b.get("level_pct"),
        "phone_temp_c": b.get("temp_c"),
        "phone_free_gb": sl.get("free_gb"),
        "motion_hz": m.get("hz"),
        "motion_shake": m.get("shake"),
        "llm_calls_today": c.get("calls_today"),
        "paid_calls_today": c.get("paid_calls_today"),
        "queue_done": len(st.get("done") or []),
        "queue_terminal": len(st.get("failed_terminal") or []),
    }


def _canon(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _entries() -> list[dict]:
    if not CHAIN.is_file():
        return []
    out = []
    for line in CHAIN.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append({"corrupt": line[:80]})
    return out


def head_hash() -> str:
    e = _entries()
    return e[-1].get("hash", GENESIS) if e else GENESIS


def append() -> dict:
    payload = snapshot()
    prev = head_hash()
    h = hashlib.sha256(prev.encode() + _canon(payload)).hexdigest()
    entry = {"ts": time.time(), "prev": prev, "payload": payload, "hash": h}
    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAIN, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def verify() -> tuple[bool, str]:
    prev = GENESIS
    for i, e in enumerate(_entries()):
        if "corrupt" in e:
            return False, f"entry {i}: unparseable line"
        if e.get("prev") != prev:
            return False, f"entry {i}: prev mismatch (chain broken here)"
        expect = hashlib.sha256(prev.encode() + _canon(e.get("payload") or {})).hexdigest()
        if e.get("hash") != expect:
            return False, f"entry {i}: payload tampered (hash mismatch)"
        prev = e["hash"]
    return True, f"{prev[:32]}..."


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "append").lower()
    if cmd == "append":
        e = append()
        print(f"appended  hash={e['hash'][:32]}...  prev={e['prev'][:16]}...")
        return 0
    if cmd == "verify":
        ok, detail = verify()
        print(("OK   " if ok else "FAIL ") + detail + f"  entries={len(_entries())}")
        return 0 if ok else 1
    if cmd == "head":
        e = _entries()
        print(f"entries={len(e)}  head={head_hash()}")
        if e:
            print(json.dumps(e[-1]["payload"], indent=2))
        return 0
    print("usage: hashchain.py append|verify|head")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
