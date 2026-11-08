import io, json, time, urllib.error, urllib.request

env = {}
for line in io.open(r"C:\ABRASAX\.env", encoding="utf-8", errors="replace"):
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, _, v = s.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")

BASE = env["JEV_BASE_URL"].rstrip("/")
KEY = env["JEV_API_KEY"]

STATE = "Patch proposes raising the supervisor health timeout from 0.6s to 2.0s."
Q = {
    "safe": {"type": "noul",
             "instructions": "Is this patch safe to apply to a production supervisor?"},
    "urgency": {"type": "score",
                "instructions": "How urgent is applying this?",
                "criteria": ["can wait", "this week", "today", "right now"]},
    "route": {"type": "choice",
              "instructions": "Which reviewer should own it?",
              "criteria": {"infra": "process supervision and liveness",
                           "ml": "model serving",
                           "release": None}},
}


def post(payload, timeout=90):
    r = urllib.request.Request(BASE + "/systemone",
                               data=json.dumps(payload).encode(), method="POST")
    r.add_header("Authorization", "Bearer " + KEY)
    r.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode()), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(700).decode(errors="replace"), time.time() - t0
    except Exception as e:
        return None, repr(e)[:200], time.time() - t0


st, body, dt = post({"model": "jev-latest", "state": STATE, "questions": Q})
print("status=%s %.2fs" % (st, dt))
if isinstance(body, dict):
    print(json.dumps(body, indent=2)[:1500])
else:
    print(body)
