"""_probe_lmstudio_matrix.py - which (address, model) pairs actually answer?

LM Studio returns HTTP 500 HTML for the providers.json default model on
http://192.168.1.28:1234/v1 while :8083 (llama.cpp) serves fine. Two variables,
one matrix: loopback vs LAN address, and the configured gemma vs the LFM2.5 that
the gateway E2E already proved.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.agents_hub import llm_router as R  # noqa: E402

ADDRESSES = ["http://127.0.0.1:1234/v1", "http://192.168.1.28:1234/v1"]
MODELS = ["gemma-4-e2b-uncensored-hauhaucs-aggressive", "liquid/lfm2.5-1.2b"]


def ask(base: str, model: str, key: str) -> str:
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "Say OK"}],
                       "max_tokens": 8, "temperature": 0}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base + "/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        return f"{r.status} served={data.get('model')} " \
               f"text={(data['choices'][0]['message'].get('content') or '')[:40]!r}"
    except urllib.error.HTTPError as exc:
        head = exc.read()[:120].decode("utf-8", "replace").replace("\n", " ")
        return f"HTTP {exc.code} {head[:100]}"
    except Exception as exc:  # noqa: BLE001
        return f"ERR {exc.__class__.__name__}: {str(exc)[:80]}"


def main() -> int:
    prov = R._config()["providers"]["lmstudio"]
    key = (R._api_keys(prov) or [""])[0]
    for base in ADDRESSES:
        for model in MODELS:
            print(f"{base:34s} {model:44s} -> {ask(base, model, key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
