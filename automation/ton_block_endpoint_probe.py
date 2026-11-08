"""Find the working TON indexer endpoint for a masterchain block by seqno.

Guessing endpoints is how a verifier ends up asserting nothing: the first
attempt returned HTTPError and the check went red for the right reason. This
probe prints status + a short body per candidate so the choice is evidence.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

SEQ = 102774100
CANDIDATES = [
    "https://tonapi.io/v2/blockchain/masterchain/{seq}",
    "https://tonapi.io/v2/blockchain/blocks/(-1,8000000000000000,{seq})",
    "https://tonapi.io/v2/blockchain/blocks/-1:8000000000000000:{seq}",
    "https://toncenter.com/api/v2/getBlockHeader?workchain=-1&shard=-9223372036854775808&seqno={seq}",
    "https://toncenter.com/api/v3/blocks?workchain=-1&shard=-9223372036854775808&seqno={seq}",
]


def probe(url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "abrasax-probe/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            print("  %-3s %s" % (r.status, url))
            print("      %s" % body[:240].replace("\n", " "))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:160].replace("\n", " ")
        print("  %-3s %s\n      %s" % (exc.code, url, detail))
    except Exception as exc:  # noqa: BLE001
        print("  ERR %s\n      %s: %s" % (url, type(exc).__name__, exc))


def main() -> int:
    for tpl in CANDIDATES:
        probe(tpl.format(seq=SEQ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
