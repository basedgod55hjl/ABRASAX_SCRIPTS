"""What does a TON transaction actually cost? Measure, do not quote.

Fees are set by validator-voted config (params 18, 20, 21, 24, 25), so the
docs give formulas and the chain gives the numbers. This pulls recent
transactions from two indexers and prints the observed total fees in TON.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

URLS = [
    "https://toncenter.com/api/v3/transactions?limit=8",
    "https://toncenter.com/api/v3/transactions?limit=8&workchain=-1",
    "https://tonapi.io/v2/blockchain/transactions?limit=8",
]


def fetch(url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        print("  HTTP %s  %s" % (exc.code, url))
        print("       %s" % exc.read().decode("utf-8", "replace")[:120])
        return
    except Exception as exc:  # noqa: BLE001
        print("  ERR %s  %s" % (type(exc).__name__, url))
        return
    rows = doc.get("transactions") if isinstance(doc, dict) else None
    if not rows:
        print("  no rows  %s  keys=%s" % (url, list(doc)[:8] if isinstance(doc, dict) else type(doc)))
        return
    print("  %d rows  %s" % (len(rows), url))
    for t in rows[:8]:
        fees = t.get("total_fees")
        if isinstance(fees, int):
            fees_ton = fees / 1e9
        else:
            fees_ton = fees
        print("    total_fees=%s TON  (%s)  aborted=%s"
              % (fees_ton, t.get("total_fees"), t.get("aborted")))


def main() -> int:
    for url in URLS:
        fetch(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
