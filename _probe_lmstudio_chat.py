"""_probe_lmstudio_chat.py - does LM Studio answer a chat completion right now?

Route probing said `lmstudio` is up (health 200) while `route="auto"` fell
through to llamacpp-local, so the chat endpoint itself must be refusing. This
prints the status and the server's own message instead of guessing.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.agents_hub import llm_router as R  # noqa: E402

BASE = "http://127.0.0.1:1234/v1"


def main() -> int:
    cfg = R._config()
    prov = cfg["providers"]["lmstudio"]
    model = R._pick_model(prov, None)
    key = (R._api_keys(prov) or [""])[0]
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "Say OK"}],
                       "max_tokens": 8, "temperature": 0}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                 headers=headers)
    print("model:", model, "base:", R._base_url(prov), "key:", bool(key))
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        print("status:", r.status)
        print("served:", data.get("model"))
        print("content:", (data["choices"][0]["message"].get("content") or "")[:80])
        return 0
    except urllib.error.HTTPError as exc:
        msg = exc.read()[:400].decode("utf-8", "replace")
        print("HTTP", exc.code, msg)
        return 1
    except Exception as exc:  # noqa: BLE001
        print("ERR", exc.__class__.__name__, exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
