"""Final model state after the load cascade. What actually works, right now.

The preload audit produced a confusing picture because a failed bonsai load evicted
lfm2.5. This re-measures everything serially with a shorter, realistic timeout and
reports the true state, including which models LM Studio lists as `loaded`.

The lesson worth recording: a failed large-model load is not free. It reserves
VRAM, fails, and can evict a working small model. On a 6 GB card with 90% already
used, attempting a 27 B model is an outage, not a slow path.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234"

TARGETS = [
    "gemma-4-e2b-uncensored-hauhaucs-aggressive",
    "text-embedding-nomic-embed-text-v1.5",
    "nvidia/nemotron-3-nano-4b",
    "prism-ml/bonsai-27b",
]


def state_of():
    try:
        with urllib.request.urlopen(f"{BASE}/api/v0/models", timeout=15) as r:
            data = json.loads(r.read().decode()).get("data", [])
        return {m["id"]: m.get("state") for m in data}
    except Exception:  # noqa: BLE001
        return {}


def probe(model, timeout=90):
    is_embed = "embed" in model.lower()
    path = "/v1/embeddings" if is_embed else "/v1/chat/completions"
    body = ({"model": model, "input": "x"} if is_embed else
            {"model": model, "messages": [{"role": "user", "content": "hi"}],
             "max_tokens": 8})
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return True, round(time.time() - t0, 1), ""
    except urllib.error.HTTPError as e:
        return False, round(time.time() - t0, 1), \
               f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:80]}"
    except Exception as e:  # noqa: BLE001
        return False, round(time.time() - t0, 1), type(e).__name__


before = state_of()
print("=== LM Studio reported states ===")
for m in TARGETS:
    print(f"  {m:44s} {before.get(m, 'not listed')}")

print("\n=== live probe (90 s timeout each, serial) ===")
results = {}
for m in TARGETS:
    ok, secs, err = probe(m)
    results[m] = {"ok": ok, "secs": secs, "error": err,
                  "state": before.get(m)}
    mark = "OK  " if ok else "FAIL"
    print(f"  {mark} {m:44s} {secs:6.1f}s  {err}")
    time.sleep(2)

after = state_of()
print("\n=== states after the probes ===")
for m in TARGETS:
    print(f"  {m:44s} {after.get(m, 'not listed')}")

serving = [m for m, r in results.items() if r["ok"]]
print(f"\n=== SERVING NOW: {len(serving)}/{len(TARGETS)} ===")
for m in serving:
    print(f"  {m}  ({results[m]['secs']}s)")

print("\n=== what a safe preload list is ===")
print("  Only models that answered above. Everything else fails the 'Engine protocol")
print("  startup was aborted' or returns 400/500, and attempting a 27 B model on this")
print("  card evicts working models when it fails.")

out = r"C:\ABRASAX\LOGS\final-model-state.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "results": results, "serving": serving,
               "states_after": after}, f, indent=2)
print(f"\nwrote {out}")
