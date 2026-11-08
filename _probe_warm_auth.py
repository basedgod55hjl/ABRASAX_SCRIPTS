"""_probe_warm_auth.py - why does the build loop's warm ping get 401?

Runs the same request three ways and prints the status + first body bytes:
  1. the key the router resolves (agents_hub.llm_router._load_env / _api_keys)
  2. the key straight from .env
  3. no key
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

URL = "http://127.0.0.1:1234/v1/chat/completions"
BODY = json.dumps({"model": "liquid/lfm2.5-1.2b",
                   "messages": [{"role": "user", "content": "ping"}],
                   "max_tokens": 2, "stream": False}).encode()


def attempt(label: str, key: str) -> None:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(URL, data=BODY, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"{label:12s} {r.status} ok  keylen={len(key)}")
    except urllib.error.HTTPError as exc:
        body = exc.read()[:160].decode("utf-8", "replace")
        print(f"{label:12s} {exc.code} {body}  keylen={len(key)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label:12s} ERR {exc.__class__.__name__}: {exc}")


def main() -> int:
    try:
        from agents.agents_hub import llm_router as R
        env = R._load_env()
        prov = (R._config().get("providers") or {}).get("lmstudio") or {}
        keys = R._api_keys(prov)
        router_key = keys[0] if keys else ""
    except Exception as exc:  # noqa: BLE001
        env, router_key = {}, ""
        print("router key lookup failed:", exc)
    dotenv_key = (env.get("LM_STUDIO_API_KEY") or env.get("LM_API_KEY")
                  or "").strip()
    print("dotenv key found:", bool(dotenv_key),
          "router key found:", bool(router_key),
          "equal:", dotenv_key == router_key)
    attempt("router-key", router_key)
    attempt("dotenv-key", dotenv_key)
    attempt("no-key", "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
