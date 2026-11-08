#!/usr/bin/env python3
"""fix_mind_route.py -- give the mind a brain that answers when the GPU is busy.

Measured 2026-11-02 00:3xZ: triune-mind reported llm_ok=0 / llm_fail=97 with
    HTTP 401 "Malformed LM Studio API token" and then HTTP 500 from LM Studio.
Root cause was not the token: the 6 GB card had 4.43 GB pinned to deepseek-r1 by the
model_pinner and GGUFF was generating against it, so the small model the mind wanted was
evicted and requests failed fast (3.4 ms). A mind whose only route is "the one local model"
is offline exactly when the machine is busy -- which is always.

The mind now walks a route list, in the order the stack itself trusts:
  1. the gateway (http://127.0.0.1:9001) with model "auto" -- i.e. the router's choice,
     bearer token from .env (the gateway refuses POSTs without it once it is not loopback);
  2. the same gateway with "nvidia:<NVIDIA_MODEL>" -- cloud fallback that does not care
     what the local card is doing;
  3. LM Studio directly, last resort.
The route that answered is recorded in memory/triune_mind.json as `last_route`, so
"the mind is up" can be read, not assumed.

Run: python SCRIPTS/fix_mind_route.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "ENGINE" / "abrasax_engine" / "triune_mind.py"

CFG_OLD = '''MODEL = os.environ.get("ABRASAX_MIND_MODEL") or ENV.get("ABRASAX_MIND_MODEL") or DEFAULT_MODEL
URL = os.environ.get("ABRASAX_MIND_URL") or ENV.get("ABRASAX_MIND_URL") or DEFAULT_URL
KEY = (
    os.environ.get("ABRASAX_MIND_KEY")
    or ENV.get("LM_STUDIO_API_KEY")
    or ENV.get("LM_API_KEY")
    or ""
)'''

CFG_NEW = '''MODEL = os.environ.get("ABRASAX_MIND_MODEL") or ENV.get("ABRASAX_MIND_MODEL") or "auto"
GATEWAY_URL = (
    os.environ.get("ABRASAX_MIND_URL")
    or ENV.get("ABRASAX_MIND_URL")
    or (os.environ.get("ABRASAX_GATEWAY_URL") or ENV.get("ABRASAX_GATEWAY_URL") or "")
    or "http://127.0.0.1:9001/v1/chat/completions"
)
LM_URL = ENV.get("LM_STUDIO_CHAT_URL") or "http://127.0.0.1:1234/v1/chat/completions"
GATEWAY_KEY = (
    os.environ.get("ABRASAX_GATEWAY_TOKEN")
    or ENV.get("ABRASAX_GATEWAY_TOKEN")
    or ""
)
LM_KEY = (
    os.environ.get("ABRASAX_MIND_KEY")
    or ENV.get("LM_STUDIO_API_KEY")
    or ENV.get("LM_API_KEY")
    or ""
)
URL = GATEWAY_URL
KEY = GATEWAY_KEY or LM_KEY

#: Tried in order. A busy card must not be able to silence the mind.
ROUTES = [
    ("gateway/auto", GATEWAY_URL, GATEWAY_KEY, MODEL),
    ("gateway/nvidia", GATEWAY_URL, GATEWAY_KEY,
     "nvidia:" + (ENV.get("NVIDIA_MODEL") or "nvidia/nemotron-3-ultra-550b-a55b")),
    ("lmstudio/direct", LM_URL, LM_KEY, "liquid/lfm2.5-1.2b"),
]
ROUTES = [r for r in ROUTES if r[1] and r[3]]'''

ASK_OLD_START = 'def ask_model(context: dict, deterministic: str) -> dict:'
ASK_NEW = '''def _one(url: str, key: str, model: str, messages: list[dict], timeout: float) -> dict:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": 120,
            "temperature": 0.7,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        text = " ".join(str(text).split())[:400]
        return {
            "ok": bool(text),
            "text": text,
            "model": data.get("model", model),
            "usage": data.get("usage"),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "error": None if text else "empty completion",
        }
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        return {"ok": False, "text": None, "model": model, "usage": None,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"HTTP {e.code}: {detail or e.reason}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "text": None, "model": model, "usage": None,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"{type(e).__name__}: {e}"}


def ask_model(context: dict, deterministic: str) -> dict:
    """Walk ROUTES until one answers. Never raises; the first success wins."""
    messages = _prompt(context, deterministic)
    attempts = []
    per_route = max(8.0, TIMEOUT / max(1, len(ROUTES)))
    for name, url, key, model in ROUTES:
        result = _one(url, key, model, messages, per_route)
        result["route"] = name
        if result["ok"]:
            result["attempts"] = attempts
            return result
        attempts.append({"route": name, "error": result["error"]})
    last = attempts[-1] if attempts else {"route": None, "error": "no routes configured"}
    return {
        "ok": False,
        "text": None,
        "model": last.get("route"),
        "usage": None,
        "latency_ms": None,
        "error": "; ".join(f"{a['route']}: {a['error']}" for a in attempts)[:500] or last["error"],
        "route": None,
        "attempts": attempts,
    }


def _unused_ask_model(context: dict, deterministic: str) -> dict:'''


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    applied = "ROUTES = [" in text and "def _one(" in text
    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"mind route chain={applied}")
        return 0 if applied else 1
    if applied:
        print("already patched: mind route chain")
        return 0

    if CFG_OLD not in text:
        print("FAIL  config block not found")
        return 1
    text = text.replace(CFG_OLD, CFG_NEW, 1)

    if ASK_OLD_START not in text:
        print("FAIL  ask_model not found")
        return 1
    text = text.replace(ASK_OLD_START, ASK_NEW, 1)

    bak = SRC.with_suffix(".py.bak-routechain")
    if not bak.exists():
        bak.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    SRC.write_text(text, encoding="utf-8")

    import py_compile

    py_compile.compile(str(SRC), doraise=True)
    print("patched triune_mind.py: gateway/auto -> gateway/nvidia -> lmstudio/direct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
