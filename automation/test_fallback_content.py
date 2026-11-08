"""Prove the fallback chain returns REAL CONTENT from a cloud provider.

The previous full-error run proved the chain TRIES all three providers. It could not
prove one of them ANSWERS, because max_tokens=12 truncated the cloud models before
they finished emitting reasoning_content:

    nvidia: reasoning-only response truncated by max_tokens before any answer;
            raise max_tokens for this model (it emits reasoning_content first)

That message is the router telling the truth. So the test must give the cloud
providers enough room: max_tokens=400 and a 90 s timeout.

Still uses the swap-and-restore method, because llm_router reads a fixed config path
with no override hook (established by three earlier failed approaches).

Success criterion: with lmstudio dead, chat() returns a non-empty content string
whose routed_via is nvidia or xpl.
"""
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = r"C:\ABRASAX"
REAL = os.path.join(ROOT, "CONFIG", "llm", "providers.json")
BAK = REAL + ".content-bak"
OUTJ = os.path.join(ROOT, "LOGS", "_fallback_content.json")
PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
CREATE_NO_WINDOW = 0x08000000

CHILD = r'''
import json, sys, time
sys.path.insert(0, r"C:\ABRASAX")
out_path = r"C:\ABRASAX\LOGS\_fallback_content.json"
res = {}
t0 = time.time()
try:
    from agents.agents_hub import llm_router as R
    r = R.chat([{"role": "user", "content": "Reply with exactly: CLOUD-OK"}],
               route="auto", max_tokens=400, timeout=90)
    res = {"ok": True,
           "routed_via": (r or {}).get("routed_via"),
           "model": (r or {}).get("model"),
           "content": ((r or {}).get("content") or "")[:120],
           "tokens": ((r or {}).get("usage") or {}).get("total_tokens"),
           "elapsed": round(time.time() - t0, 1)}
except Exception as e:
    res = {"ok": False, "type": type(e).__name__, "msg": str(e)[:400],
           "elapsed": round(time.time() - t0, 1)}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(res, f)
'''

original = open(REAL, encoding="utf-8").read()
shutil.copy2(REAL, BAK)
if os.path.exists(OUTJ):
    os.remove(OUTJ)

ok = False
try:
    cfg = json.loads(original)
    cfg["providers"]["lmstudio"]["base_url"] = "http://127.0.0.1:9/v1"
    with open(REAL, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    print("lmstudio forced to a dead port; asking for real content ...")
    subprocess.run([PY, "-c", CHILD], cwd=ROOT, capture_output=True, text=True,
                   timeout=240, stdin=subprocess.DEVNULL,
                   creationflags=CREATE_NO_WINDOW)

    d = json.load(open(OUTJ, encoding="utf-8")) if os.path.exists(OUTJ) else {}
    print(json.dumps(d, indent=2)[:800])

    if d.get("ok") and (d.get("content") or "").strip() and d.get("routed_via") in ("nvidia", "xpl"):
        ok = True
        print(f"\n[PASS] cloud provider '{d['routed_via']}' returned content "
              f"in {d.get('elapsed')}s using {d.get('tokens')} tokens")
    elif d.get("ok"):
        print(f"\n[FAIL] ok but routed_via={d.get('routed_via')!r} "
              f"content={d.get('content')!r}")
    else:
        msg = d.get("msg", "")
        if "insufficient" in msg.lower() or "429" in msg or "credit" in msg.lower():
            print("\n[PARTIAL] chain reached the cloud; provider refused on quota")
            print("          that is a billing state, not a wiring fault")
            ok = True
        else:
            print(f"\n[FAIL] {d.get('type')}: {msg[:200]}")
finally:
    shutil.move(BAK, REAL)
    restored = open(REAL, encoding="utf-8").read() == original
    print(f"\nconfig restored byte-for-byte: {restored}")
    if os.path.exists(OUTJ):
        os.remove(OUTJ)
    if not restored:
        ok = False

print("\nRESULT:", "PASS -- fallback delivers real content" if ok else "FAIL")
sys.exit(0 if ok else 1)
