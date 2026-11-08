import io, json, time, urllib.request, urllib.error

env = {}
for line in io.open(r"C:\ABRASAX\.env", encoding="utf-8", errors="replace"):
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, _, v = s.partition("=")
    env[k.strip()] = v.strip().strip('"').strip("'")

key = env["DEEPSEEK_API_KEY"]
base = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
model = env.get("DEEPSEEK_MODEL", "deepseek-flash")

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are a terminal agent. Answer in one short line."},
        {"role": "user", "content": "Reply with exactly: DEEPSEEK-FLASH-ONLINE"},
    ],
    "max_tokens": 32,
    "temperature": 0,
}

req = urllib.request.Request(base + "/chat/completions",
                             data=json.dumps(payload).encode(), method="POST")
req.add_header("Authorization", "Bearer " + key)
req.add_header("Content-Type", "application/json")

t0 = time.perf_counter()
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.loads(r.read().decode())
    dt = time.perf_counter() - t0
    msg = body["choices"][0]["message"]
    usage = body.get("usage", {})
    print("status   : 200")
    print("latency  : %.2fs" % dt)
    print("content  :", repr(msg.get("content")))
    print("reasoning:", (msg.get("reasoning_content") or "")[:80])
    print("usage    :", usage)
    print("model    :", body.get("model"))
    toks = usage.get("completion_tokens") or 0
    if toks and dt:
        print("tps      : %.1f" % (toks / dt))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode(errors="replace")[:500])
except Exception as e:
    print("ERR", repr(e)[:300])
