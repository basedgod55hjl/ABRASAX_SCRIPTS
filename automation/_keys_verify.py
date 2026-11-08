import io, json, time, urllib.request, urllib.error

env = {}
for line in io.open(r"C:\ABRASAX\.env", encoding="utf-8", errors="replace"):
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, _, v = s.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")


def req(url, key, payload=None, timeout=45, method=None):
    data = json.dumps(payload).encode() if payload else None
    r = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    r.add_header("Authorization", "Bearer " + key)
    r.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read(600).decode(errors="replace"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode(errors="replace"), time.time() - t0
    except Exception as e:
        return None, type(e).__name__ + ": " + str(e)[:100], time.time() - t0


print("=== NVIDIA key 1 ===")
nv = env.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
for k in ("NVIDIA_API_KEY_1", "NVIDIA_API_KEY_2"):
    st, body, dt = req(nv + "/models", env[k])
    print("%-18s %-5s %.1fs %s" % (k, st, dt, body[:120].replace("\n", " ")))

print("\n=== JEV ===")
jev = env.get("JEV_BASE_URL", "https://api.typesafe.ai/v1")
for path in ("/models", "/systemone"):
    st, body, dt = req(jev + path, env["JEV_API_KEY"])
    print("%-14s %-5s %.1fs %s" % (path, st, dt, body[:140].replace("\n", " ")))

print("\n=== GitHub PAT ===")
GHPAT = "REDACTED_REVOKE_IN_GITHUB_SETTINGS"
r = urllib.request.Request("https://api.github.com/user")
r.add_header("Authorization", "Bearer " + GHPAT)
r.add_header("Accept", "application/vnd.github+json")
r.add_header("User-Agent", "abrasax")
try:
    with urllib.request.urlopen(r, timeout=25) as resp:
        d = json.loads(resp.read().decode())
        print("200 login=%s id=%s" % (d.get("login"), d.get("id")))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read(200).decode(errors="replace"))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:100])
