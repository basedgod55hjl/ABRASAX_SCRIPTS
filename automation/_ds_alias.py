import json, sys, time, urllib.request

def post(model, prompt="Reply exactly: ALIAS-OK"):
    req = urllib.request.Request("http://127.0.0.1:9001/v1/chat/completions",
                                 data=json.dumps({
                                     "model": model,
                                     "messages": [{"role": "user", "content": prompt}],
                                     "max_tokens": 24, "temperature": 0,
                                 }).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            b = json.loads(r.read().decode())
        return r.status, b.get("model"), repr(b["choices"][0]["message"]["content"])[:80], time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode(errors="replace")[:120], time.perf_counter() - t0
    except Exception as e:
        return None, None, repr(e)[:120], time.perf_counter() - t0

for m in ("deepseek-flash", "deepseek", "deepseek-chat", "deepseek-reasoner", "nevotron"):
    st, served, body, dt = post(m)
    print("%-18s -> %-4s served=%-16s %.2fs %s" % (m, st, served, dt, body))
