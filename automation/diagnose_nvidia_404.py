"""Why does nvidia return 404 for a model that IS in its catalogue?

MEASURED
  /v1/models with NVIDIA_API_KEY_1 returns 81 models, and the configured default
  `nvidia/nemotron-3-super-120b-a12b` DOES appear in that list.
  Yet the router's own error says:
      nvidia: 404 Client Error: Not Found for url:
              https://integrate.api.nvidia.com/v1/chat/completions
  twice (both keys).

A 404 on /chat/completions while /models lists the model means the failure is not
"unknown model". Candidates:
  a  the key is not entitled to that model (NVIDIA returns 404 rather than 403 for
     some entitlements)
  b  the request body is rejected in a way that surfaces as 404
  c  the second key is invalid and the first is fine -- but BOTH returned 404

Test the actual call directly, with each key, printing the full response body.
Never trust a truncated error.
"""
import json
import os
import urllib.error
import urllib.request

URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

keys = []
for name in ("NVIDIA_API_KEY_1", "NVIDIA_API_KEY_2", "NVIDIA_API_KEY"):
    v = os.environ.get(name)
    if v:
        keys.append((name, v))

if not keys:
    print("no NVIDIA key in the environment")
    raise SystemExit(0)

print(f"testing {len(keys)} key(s) against {MODEL}\n")

for name, key in keys:
    masked = key[:10] + "..." + key[-4:] if len(key) > 16 else "short"
    print("=" * 74)
    print(f"{name}  {masked}  (len {len(key)})")

    # 1. can the key see models at all?
    try:
        req = urllib.request.Request("https://integrate.api.nvidia.com/v1/models",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        ids = [m["id"] for m in data.get("data", [])]
        print(f"  /v1/models  : {r.status}  {len(ids)} models  "
              f"target present={MODEL in ids}")
    except urllib.error.HTTPError as e:
        print(f"  /v1/models  : HTTP {e.code}  {e.read()[:160]}")
        continue
    except Exception as e:  # noqa: BLE001
        print(f"  /v1/models  : {type(e).__name__}: {e}")
        continue

    # 2. the actual chat call, both with and without extra fields
    for label, body in (
        ("minimal", {"model": MODEL,
                     "messages": [{"role": "user", "content": "hi"}],
                     "max_tokens": 4}),
        ("with stream:false", {"model": MODEL,
                               "messages": [{"role": "user", "content": "hi"}],
                               "max_tokens": 4, "stream": False}),
    ):
        data = json.dumps(body).encode()
        req = urllib.request.Request(URL, data=data, method="POST",
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json",
                                              "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                payload = json.loads(r.read().decode())
                content = payload.get("choices", [{}])[0].get("message", {}).get("content")
                print(f"  chat [{label:16s}]: {r.status}  content={content!r}")
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "replace")
            print(f"  chat [{label:16s}]: HTTP {e.code}  {body_text[:300]}")
        except Exception as e:  # noqa: BLE001
            print(f"  chat [{label:16s}]: {type(e).__name__}: {str(e)[:160]}")
    print()
