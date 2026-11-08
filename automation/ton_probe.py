"""Live probes: TON public indexers, TON liteserver-less HTTP APIs, Telegram bot.

Keeps secrets out of argv and out of stdout: the token is read from .env and
only the *result* (bot username / id) is printed. Every probe is bounded and
failure is reported as data, not an exception, because this runs as part of a
report whose value is the ground truth it contains.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def get(url: str, timeout: float = 20.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {"ok": True, "status": r.status,
                    "body": json.loads(r.read().decode("utf-8", "replace"))}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code,
                "body": exc.read().decode("utf-8", "replace")[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "body": "%s: %s" % (type(exc).__name__, exc)}


def env(name: str) -> str:
    try:
        with open(r"C:\abrasax\.env", "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def main() -> int:
    print("== TON indexers, three independent views ==")
    probes = {
        "toncenter_v3_masterchain": "https://toncenter.com/api/v3/masterchainInfo",
        "toncenter_v2_masterchain": "https://toncenter.com/api/v2/getMasterchainInfo",
        "tonapi_v2_status": "https://tonapi.io/v2/status",
        "tonapi_v2_masterchain_head": "https://tonapi.io/v2/blockchain/masterchain-head",
        "toncenter_v3_blocks": "https://toncenter.com/api/v3/blocks?workchain=-1&shard=-9223372036854775808&limit=1",
    }
    seqnos = {}
    for name, url in probes.items():
        t0 = time.time()
        res = get(url)
        dt_ms = round((time.time() - t0) * 1000)
        body = res.get("body")
        head = ""
        seq = None
        if isinstance(body, dict):
            flat = json.dumps(body)[:220]
            head = flat
            for key in ("seqno", "last", "last_known_masterchain_seqno"):
                node = body.get(key)
                if isinstance(node, int):
                    seq = node
                    break
                if isinstance(node, dict):
                    for k2 in ("seqno", "last_masterchain_seqno"):
                        if isinstance(node.get(k2), int):
                            seq = node[k2]
                            break
        else:
            head = str(body)[:220]
        if seq is None and isinstance(body, dict):
            blocks = body.get("blocks")
            if isinstance(blocks, list) and blocks:
                seq = blocks[0].get("seqno")
        if seq is not None:
            seqnos[name] = seq
        print("  %-26s %-4s %5sms seqno=%s" % (name, res.get("status"), dt_ms,
                                               seq if seq is not None else "?"))

    if seqnos:
        vals = list(seqnos.values())
        print("  agreement: min=%d max=%d spread=%d (%s)"
              % (min(vals), max(vals), max(vals) - min(vals),
                 "ok" if max(vals) - min(vals) <= 5 else "DISAGREE"))

    print("\n== Telegram bot (token from .env, never printed) ==")
    tok = env("ABRASAX_TELEGRAM_TOKEN")
    chat = env("ABRASAX_TELEGRAM_CHAT_ID")
    print("  token configured: %s (%d chars)  chat configured: %s"
          % (bool(tok), len(tok), bool(chat)))
    if tok:
        res = get("https://api.telegram.org/bot%s/getMe" % tok, timeout=20)
        body = res.get("body") or {}
        if res.get("ok") and isinstance(body, dict) and body.get("ok"):
            r = body.get("result", {})
            print("  getMe ok  id=%s  username=@%s  is_bot=%s"
                  % (r.get("id"), r.get("username"), r.get("is_bot")))
        else:
            print("  getMe FAILED %s %s" % (res.get("status"), str(body)[:160]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
