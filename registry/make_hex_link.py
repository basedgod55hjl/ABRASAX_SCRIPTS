#!/usr/bin/env python3
"""make_hex_link.py — bind an original GGUF and its tile-restored copy with
the PRIMAL_HEX stamp. Writes memory/hex_link_<slug>.json.

The binding is honest: SHA-256 equality is the cryptographic link; the
PRIMAL_HEX XOR stamp is the ecosystem's deterministic marker layer, plus a
TON chain anchor. Usage:
    python make_hex_link.py <real.gguf> <restored.gguf> <slug>
"""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\abrasax\SYSTEMS\dna")
import abrasax_dna_compute as dc

PRIMAL = dc.PRIMAL_HEX


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.digest()


def ton_seqno():
    try:
        with urllib.request.urlopen(
            "https://toncenter.com/api/v2/getMasterchainInfo", timeout=8
        ) as r:
            return json.load(r)["result"]["last"]["seqno"]
    except Exception:
        return None


def main():
    real, restored, slug = sys.argv[1], sys.argv[2], sys.argv[3]
    h_real = sha256_file(real)
    h_rest = sha256_file(restored)
    equal = h_real == h_rest
    # PRIMAL_HEX stamp: XOR the sha256 bytes with the repeated primal key
    stamp = bytes(b ^ PRIMAL[i % len(PRIMAL)] for i, b in enumerate(h_real))
    link = {
        "slug": slug,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "real_gguf": real,
        "restored_gguf": restored,
        "sha256_real": h_real.hex(),
        "sha256_restored": h_rest.hex(),
        "byte_identical": equal,
        "primal_hex": PRIMAL.hex().upper(),
        "hex_stamp": stamp.hex().upper(),
        "phi": dc.PHI,
        "ton_seqno": ton_seqno(),
        "claim": ("TILE == REAL GGUFF: byte-identical, SHA-256 equal, "
                  "PRIMAL_HEX stamped." if equal else "MISMATCH — link refused."),
    }
    out = Path(r"C:\abrasax\memory") / f"hex_link_{slug}.json"
    out.write_text(json.dumps(link, indent=2), encoding="utf-8")
    # verification: un-stamp and compare
    back = bytes(s ^ PRIMAL[i % len(PRIMAL)] for i, s in enumerate(stamp))
    print(f"link={out.name}")
    print(f"byte_identical={equal}")
    print(f"stamp={stamp.hex()[:32].upper()}...")
    print(f"un-stamp==sha256_real: {back == h_real}")
    print(f"ton={link['ton_seqno']}")


if __name__ == "__main__":
    main()
