"""Find a keyless endpoint that exposes raw transactions, so fees are measured.

toncenter v3 /transactions answers 403 code 1010 without an API key, and
tonapi's /v2/blockchain/transactions does not exist. Rather than quoting a doc
formula as if it were an observation, probe the block-scoped variants.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

HEAD = "https://tonapi.io/v2/blockchain/masterchain-head"


def get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:120]
    except Exception as exc:  # noqa: BLE001
        return None, "%s: %s" % (type(exc).__name__, exc)


def main() -> int:
    status, doc = get(HEAD)
    seq = doc.get("seqno") if isinstance(doc, dict) else None
    print("head:", status, seq)
    if not seq:
        return 1
    candidates = [
        "https://tonapi.io/v2/blockchain/blocks/(-1,8000000000000000,%d)/transactions" % seq,
        "https://tonapi.io/v2/blockchain/masterchain/%d/transactions" % seq,
        "https://tonapi.io/v2/blockchain/blocks/%d/transactions" % seq,
    ]
    for url in candidates:
        status, doc = get(url)
        if status == 200 and isinstance(doc, dict):
            rows = doc.get("transactions") or []
            print("OK   %s  rows=%d" % (url, len(rows)))
            for t in rows[:6]:
                fees = t.get("total_fees")
                print("     total_fees=%s (%s TON) aborted=%s"
                      % (fees, (fees / 1e9 if isinstance(fees, int) else "?"),
                         t.get("aborted")))
            if rows:
                return 0
        else:
            print("MISS %s -> %s %s" % (url, status, str(doc)[:90]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
