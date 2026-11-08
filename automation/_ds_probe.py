import io, json, os, urllib.request, urllib.error

env = {}
for line in io.open(r"C:\ABRASAX\.env", encoding="utf-8", errors="replace"):
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, _, v = s.partition("=")
    env[k.strip()] = v.strip().strip('"').strip("'")

key = env.get("DEEPSEEK_API_KEY", "")
base = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
print("base_url :", base)
print("model    :", env.get("DEEPSEEK_MODEL"))
print("key      : len=%d prefix=%s..." % (len(key), key[:6]))


def call(path, payload=None, timeout=30):
    url = base + path
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        return e.code, body
    except Exception as e:
        return None, repr(e)[:300]


print("\n--- GET /models ---")
st, body = call("/models")
print("status:", st)
if isinstance(body, dict):
    ids = [m.get("id") for m in body.get("data", [])]
    print("models:", ids)
else:
    print(body)
