"""Measure real TON fees on a busy basechain account (USDT jetton master).

Masterchain blocks carried transactions with total_fees=0 (system transactions
settle elsewhere), so the measurement has to come from basechain activity.
Printing observed values beats quoting the fee formula.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

USDT_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
URL = ("https://toncenter.com/api/v2/getTransactions?address=%s&limit=10"
       % USDT_MASTER)


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=30) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        print("HTTP %s %s" % (exc.code, exc.read().decode("utf-8", "replace")[:140]))
        return 1
    except Exception as exc:  # noqa: BLE001
        print("%s: %s" % (type(exc).__name__, exc))
        return 1
    result = doc.get("result") or []
    print("transactions: %d" % len(result))
    fees = []
    for t in result:
        f = t.get("fee")
        if isinstance(f, (int, str)) and str(f).isdigit():
            f = int(f); fees.append(f)
            print("  lt=%s  fee=%d nanotons (%.9f TON)  aborted=%s"
                  % (t.get("transaction_id", {}).get("lt"), f, f / 1e9,
                     t.get("aborted")))
    if fees:
        print("mean fee: %.6f TON over %d transactions"
              % (sum(fees) / len(fees) / 1e9, len(fees)))
        print("max fee:  %.6f TON" % (max(fees) / 1e9))
    return 0 if fees else 1


if __name__ == "__main__":
    raise SystemExit(main())
