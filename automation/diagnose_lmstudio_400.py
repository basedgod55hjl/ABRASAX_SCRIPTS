"""Did build_loop's own edit to llm_router break the lmstudio route?

TIMELINE
  before the edit: lmstudio returned 500 (JIT load aborts)
  build_loop's self-improvement landed this in AGENTS/agents_hub/llm_router.py:
        if name == "lmstudio":
            payload.setdefault("reasoning_effort", "none")
            payload["max_tokens"] = max(int(payload.get("max_tokens", 1024)), 2048)
  after  the edit: lmstudio returns 400 Bad Request

A 400 is a different class of failure from a 500. 400 means LM Studio rejected the
REQUEST, and the most likely reason is that `reasoning_effort` is not an accepted
field on this endpoint, or `max_tokens` 2048 exceeds what the resident model allows.

This measures it three ways:
  1  direct call WITHOUT reasoning_effort  -> does it succeed?
  2  direct call WITH reasoning_effort=none -> does it 400?
  3  the exact body the router now sends, printed

If (1) works and (2) 400s, build_loop's "improvement" is a regression and must be
reverted or guarded.
"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234"
MODEL = "liquid/lfm2.5-1.2b"     # a resident, known-good model


def post(body, timeout=90):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=data,
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
            msg = payload.get("choices", [{}])[0].get("message", {})
            return r.status, msg.get("content"), "", round(time.time() - t0, 1)
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode("utf-8", "replace")[:300], round(time.time() - t0, 1)
    except Exception as e:  # noqa: BLE001
        return None, None, f"{type(e).__name__}: {e}"[:200], round(time.time() - t0, 1)


BASE_BODY = {"model": MODEL,
             "messages": [{"role": "user", "content": "say hi"}],
             "temperature": 0.7, "stream": False}

CASES = [
    ("no reasoning_effort, max_tokens=64",
     dict(BASE_BODY, max_tokens=64)),
    ("reasoning_effort=none, max_tokens=64",
     dict(BASE_BODY, max_tokens=64, reasoning_effort="none")),
    ("reasoning_effort=none, max_tokens=2048  (what the router sends)",
     dict(BASE_BODY, max_tokens=2048, reasoning_effort="none")),
    ("no reasoning_effort, max_tokens=2048",
     dict(BASE_BODY, max_tokens=2048)),
]

print(f"=== lmstudio field acceptance (model {MODEL}) ===\n")
print(f"{'case':52s} {'http':>5} {'secs':>5}  result")
print("-" * 100)

results = {}
for label, body in CASES:
    st, content, err, secs = post(body)
    results[label] = (st, content, err)
    short = (content or err or "")[:36].replace("\n", " ")
    print(f"{label:52s} {str(st):>5} {secs:>5}  {short}")
    time.sleep(1.5)

print("\n=== VERDICT ===")
plain_ok = results[CASES[0][0]][0] == 200
effort_ok = results[CASES[1][0]][0] == 200
router_ok = results[CASES[2][0]][0] == 200

print(f"  plain request works              : {plain_ok}")
print(f"  reasoning_effort accepted        : {effort_ok}")
print(f"  the router's exact body accepted : {router_ok}")

if plain_ok and not effort_ok:
    print("\n  REGRESSION CONFIRMED: build_loop's reasoning_effort edit makes lmstudio")
    print("  reject the request with 400. The edit fixed a 500 and introduced a 400.")
    print("  The correct guard is to send reasoning_effort ONLY when the model is")
    print("  known to accept it, or to retry without it on 400.")
elif plain_ok and effort_ok and not router_ok:
    print("\n  PARTIAL: reasoning_effort is accepted, but max_tokens=2048 is not.")
elif router_ok:
    print("\n  NO REGRESSION: the router's body is accepted. The 400 in the ledger")
    print("  must come from a different model alias, not from this field.")

# what does the router actually pick for a typical agent call?
print("\n=== what model does the router choose? ===")
import sys
sys.path.insert(0, r"C:\ABRASAX")
try:
    from agents.agents_hub import llm_router as R
    cfg = R._config()
    prov = cfg["providers"]["lmstudio"]
    for alias in (None, "fast", "default", "reason", "reasoning", "heavy"):
        try:
            print(f"  _pick_model(alias={alias!r}) -> {R._pick_model(prov, alias)}")
        except Exception as e:  # noqa: BLE001
            print(f"  _pick_model({alias!r}) raised {type(e).__name__}: {e}")
    print(f"\n  max_tokens the caller must supply: agents use the default 1024,")
    print(f"  which the router then raises to 2048 for lmstudio.")
except Exception as e:  # noqa: BLE001
    print(f"  could not inspect router: {type(e).__name__}: {e}")
