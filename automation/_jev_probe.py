import io, json, time, urllib.error, urllib.request

env = {}
for line in io.open(r"C:\ABRASAX\.env", encoding="utf-8", errors="replace"):
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, _, v = s.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")

JEV = env["JEV_BASE_URL"].rstrip("/")
KEY = env["JEV_API_KEY"]


def call(path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload else None
    r = urllib.request.Request(JEV + path, data=data, method="POST" if data else "GET")
    r.add_header("Authorization", "Bearer " + KEY)
    r.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read(900).decode(errors="replace"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(600).decode(errors="replace"), time.time() - t0
    except Exception as e:
        return None, type(e).__name__ + ": " + str(e)[:120], time.time() - t0


print("=== /models ===")
st, body, dt = call("/models")
print(st, "%.2fs" % dt)
print(body[:700])

print("\n=== try /systemone shapes ===")
tries = [
    ("/systemone", {"question": "Is this patch safe?", "kind": "noul",
                    "criteria": "Does it avoid hacks?"}),
    ("/systemone", {"state": "patch proposes changing a timeout", "question": "safe?"}),
    ("/chat/completions", {"model": "jev-latest",
                           "messages": [{"role": "user", "content": "Answer OK"}],
                           "max_tokens": 16}),
]
for path, payload in tries:
    st, body, dt = call(path, payload)
    print("\n%-20s %-5s %.2fs" % (path, st, dt))
    print("  ", body[:400].replace("\n", " "))
