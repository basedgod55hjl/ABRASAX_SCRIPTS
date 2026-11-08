"""The build queue asks for model="bonsai"; that alias resolves to a model that will not load.

CAUSAL CHAIN, now complete

  LOGS/build-queue.jsonl
      {"id":"self-002","kind":"agent","agent_id":"code-reviewer","model":"bonsai", ...}
      {"id":"self-003","kind":"agent","agent_id":"test-engineer","model":"bonsai", ...}

  build_loop.py:136   model=item.get("model")     -> "bonsai" is forwarded verbatim

  llm_router._pick_model(prov, "bonsai") -> prism-ml/bonsai-27b   (3627 MB GGUF)

  prism-ml/bonsai-27b is listed in /v1/models, but every attempt to have it serve a
  request fails:
      earlier serial probe: HTTP 500
      diagnose_model_load_failures: JIT load aborts with
          "Engine protocol startup was aborted"

  So the loop is not failing because of the router, the credentials, or
  build_loop's own edit (that edit is correct -- reasoning_effort and
  max_tokens=2048 are both accepted, verified 200/200).

  It fails because the queue hardcodes an alias for a model the engine cannot start.

VERIFY, THEN FIX

  The fix has two independent parts, and both must be justified:
    a  the queue entries should not pin a model that cannot load
    b  the router should fail over to a model that CAN serve, rather than letting a
       pinned-but-dead alias kill the whole task

  (b) is the more valuable change because a pinned alias will happen again. But it
  changes router semantics, so measure first: does bonsai really fail right now, and
  does the same task succeed with the working model?
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234"
sys.path.insert(0, r"C:\ABRASAX")

print("=== 1. is prism-ml/bonsai-27b serving right now? ===")


def probe(model, timeout=180):
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "say hi"}],
                       "max_tokens": 8}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
            c = d.get("choices", [{}])[0].get("message", {}).get("content")
            return r.status, c, "", round(time.time() - t0, 1)
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode("utf-8", "replace")[:200], round(time.time() - t0, 1)
    except Exception as e:  # noqa: BLE001
        return None, None, f"{type(e).__name__}"[:80], round(time.time() - t0, 1)


st, c, err, secs = probe("prism-ml/bonsai-27b")
print(f"  prism-ml/bonsai-27b : HTTP {st}  {secs}s  "
      f"{'OK ' + repr(c)[:40] if c else err}")
bonsai_ok = st == 200

time.sleep(2)

print("\n=== 2. same task, working model ===")
st2, c2, err2, secs2 = probe("liquid/lfm2.5-1.2b")
print(f"  liquid/lfm2.5-1.2b  : HTTP {st2}  {secs2}s  "
      f"{'OK ' + repr(c2)[:40] if c2 else err2}")
lfm_ok = st2 == 200

print("\n=== 3. what does the alias resolve to? ===")
from agents.agents_hub import llm_router as R
prov = R._config()["providers"]["lmstudio"]
for alias in ("bonsai", "reasoning", "primary", "heavy", None):
    print(f"  alias={str(alias):10s} -> {R._pick_model(prov, alias)}")

print("\n=== VERDICT ===")
print(f"  bonsai serves      : {bonsai_ok}")
print(f"  lfm2.5 serves      : {lfm_ok}")
if not bonsai_ok and lfm_ok:
    print("\n  CONFIRMED: the queue pins 'bonsai', which cannot load, while another")
    print("  model on the same server answers in ~0.3 s. The build loop is stalled")
    print("  by a model alias, not by the router or the credentials.")
    print("\n  Two candidate remedies, both needing a decision:")
    print("    a) edit LOGS/build-queue.jsonl to drop the pinned model")
    print("       -- fixes these two items only; the next producer repeats it")
    print("    b) make the router treat a pinned-but-unloadable model as a fallback")
    print("       trigger -- fixes the class, changes router semantics")
else:
    print("\n  the pinned model is not the cause; investigate further")
