import json, time, urllib.request, urllib.error

def post(url, payload, timeout=60, key=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode()), time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300], time.perf_counter() - t0
    except Exception as e:
        return None, repr(e)[:200], time.perf_counter() - t0


for model in ("deepseek-flash", "deepseek"):
    st, body, dt = post("http://127.0.0.1:9001/v1/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": "Reply exactly: GW-FLASH-OK"}],
        "max_tokens": 32, "temperature": 0,
    })
    print("model=%-14s status=%-4s %.2fs" % (model, st, dt))
    if isinstance(body, dict):
        try:
            print("   content:", repr(body["choices"][0]["message"]["content"])[:160])
            print("   served :", body.get("model"))
        except Exception:
            print("   body:", json.dumps(body)[:250])
    else:
        print("   body:", body)
