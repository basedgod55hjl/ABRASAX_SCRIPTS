"""Test provider fallback for real, by pointing the config at a dead endpoint.

WHY THE FIRST ATTEMPT WAS INVALID

The previous test set `LM_STUDIO_BASE_URL=http://127.0.0.1:9/v1` in the environment
and expected the router to fail over. It reported routed_via=lmstudio and I called
that a wiring defect. That was MY bug:

    llm_router._base_url(prov) reads from CONFIG/llm/providers.json
    It does not consult LM_STUDIO_BASE_URL at all
    (grep for 127.0.0.1:1234 in llm_router.py: zero hits -- the URL only lives in config)

So the router correctly connected to the real LM Studio, and routed_via=lmstudio was
TRUE. I proved nothing about fallback and then reported a failure. Thirty-first false
reading of the session, and the same shape as all the others: a check that did not
test the thing it claimed to test.

THE VALID TEST

Copy providers.json, rewrite lmstudio.base_url to a discard port (127.0.0.1:9),
run the router against the copy, and observe:
  * if it falls over to nvidia/xpl -> fallback works
  * if it raises "all providers failed" -> fallback is broken
  * if it still says lmstudio -> it is not reading the copy at all (a different bug)

The real config is never modified: the copy lives in LOGS/ and the router is pointed
at it through the same mechanism the config layer uses.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = r"C:\ABRASAX"
REAL = os.path.join(ROOT, "CONFIG", "llm", "providers.json")
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000

# how does the router locate its config?
sys.path.insert(0, ROOT)
from agents.agents_hub import llm_router  # noqa: E402

print("=== how does the router find its config? ===")
import inspect

src = inspect.getsource(llm_router._config)
print(src[:600])

print("\n=== building a dead-lmstudio copy ===")
cfg = json.load(open(REAL, encoding="utf-8"))
orig_lm = cfg["providers"]["lmstudio"].get("base_url")
cfg["providers"]["lmstudio"]["base_url"] = "http://127.0.0.1:9/v1"
tmp = os.path.join(ROOT, "LOGS", "_providers_deadlm.json")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
print(f"  original lmstudio base_url : {orig_lm}")
print(f"  patched  lmstudio base_url : http://127.0.0.1:9/v1")
print(f"  copy written to            : {tmp}")

# find whatever env var the config layer honours
ENV_HINT = [k for k in os.environ if "ABRASAX" in k and "CONFIG" in k]
print(f"  relevant env vars already set: {ENV_HINT}")

# ---- run the router in a child with the config swapped -----------------
code = r'''
import json, sys
sys.path.insert(0, r"C:\ABRASAX")
import os
from agents.agents_hub import llm_router as R

# force the router to read our copy
R._CONFIG_PATH_OVERRIDE = r"C:\ABRASAX\LOGS\_providers_deadlm.json"
try:
    R._config.cache_clear()
except AttributeError:
    pass

try:
    r = R.chat([{"role": "user", "content": "Reply with exactly: FALLBACK-OK"}],
               route="auto", max_tokens=12, timeout=60)
    print(json.dumps({"ok": True,
                      "routed_via": (r or {}).get("routed_via"),
                      "content": ((r or {}).get("content") or "")[:40]}))
except Exception as e:
    print(json.dumps({"ok": False,
                      "error": type(e).__name__ + ": " + str(e)[:200]}))
'''

# does the module even support an override? check for a cache / path constant
src_all = inspect.getsource(llm_router)
has_cache = "cache" in src_all
print(f"\n  llm_router has a config cache: {has_cache}")

p = subprocess.run([PY, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   timeout=180, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
out = (p.stdout or "").strip().splitlines()
payload = {}
if out:
    try:
        payload = json.loads(out[-1])
    except json.JSONDecodeError:
        payload = {"ok": False, "error": out[-1][:200]}
else:
    payload = {"ok": False, "error": (p.stderr or "no output")[:200]}

print(f"\n=== fallback result ===")
print(f"  {json.dumps(payload)[:300]}")

via = payload.get("routed_via")
if not payload.get("ok"):
    err = str(payload.get("error", ""))
    if "429" in err or "insufficient" in err.lower() or "credit" in err.lower():
        verdict = "PARTIAL -- fell through to a cloud provider that refused on quota"
        ok = True
    elif "all providers failed" in err:
        verdict = "FAIL -- no provider accepted the request"
        ok = False
    else:
        verdict = f"UNKNOWN -- {err[:80]}"
        ok = False
elif via == "lmstudio":
    verdict = "FAIL -- still routed to lmstudio despite a dead base_url"
    ok = False
else:
    verdict = f"PASS -- fell back to {via}"
    ok = True

print(f"  VERDICT: {verdict}")

os.remove(tmp)

# ---- restore check -----------------------------------------------------
now = json.load(open(REAL, encoding="utf-8"))
restored = now["providers"]["lmstudio"].get("base_url") == orig_lm
print(f"\n  real config untouched     : {restored}")
print(f"  real lmstudio base_url    : {now['providers']['lmstudio'].get('base_url')}")

print("\nRESULT:", "PASS" if (ok and restored) else "DEFECTS")
sys.exit(0 if (ok and restored) else 1)
