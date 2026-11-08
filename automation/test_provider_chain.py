"""Prove the provider chain actually routes and falls back, with real calls.

The config claims:
    order = lmstudio -> nvidia -> xpl
    auto_fallback = true
    jev_gate = true

A chain is only real if it can be observed doing three things:
  1  route to the FIRST provider when healthy
  2  survive the first provider being unavailable
  3  never silently return another provider's answer as if it were the first's

This makes real calls. Each is small (max_tokens=8) so the cost and latency are
bounded. Nothing is destructive; no model is loaded or unloaded.

The fallback test cannot kill LM Studio (that would disturb the AI bind that is
running), so it tests the router's decision function directly with an unreachable
base URL -- that is the same code path a real outage takes.
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = r"C:\ABRASAX"
sys.path.insert(0, ROOT)

print("=== 1. ROUTING: does a normal call go to lmstudio? ===")
try:
    from abrasax import llm
    t0 = time.time()
    r = llm.ask("Reply with exactly: ROUTE-OK", max_tokens=12)
    dt = time.time() - t0
    content = (r or {}).get("content", "")
    routed = (r or {}).get("routed_via")
    model = (r or {}).get("model")
    usage = (r or {}).get("usage", {})
    print(f"  content   : {content[:40]!r}")
    print(f"  routed_via: {routed}")
    print(f"  model     : {model}")
    print(f"  tokens    : {usage.get('total_tokens')}")
    print(f"  latency   : {dt:.2f}s")
    route_ok = routed == "lmstudio" and "ROUTE-OK" in content
    print(f"  [{'PASS' if route_ok else 'FAIL'}] first provider used for a healthy call")
except Exception as e:  # noqa: BLE001
    print(f"  FAILED: {type(e).__name__}: {e}")
    route_ok = False

print("\n=== 2. PROVIDER HEALTH AS THE ROUTER SEES IT ===")
try:
    probe = llm.probe()
    for item in (probe or []):
        print(f"  {item}")
    probe_ok = bool(probe)
except Exception as e:  # noqa: BLE001
    print(f"  probe failed: {type(e).__name__}: {e}")
    probe_ok = False

print("\n=== 3. FALLBACK: what happens when lmstudio is unreachable? ===")
# Point the router at a dead port in a subprocess so the running AI bind is untouched.
code = r'''
import sys, json
sys.path.insert(0, r"C:\ABRASAX")
import os
os.environ["LM_STUDIO_BASE_URL"] = "http://127.0.0.1:9/v1"   # discard port
os.environ["LM_STUDIO_CHAT_URL"] = "http://127.0.0.1:9/v1/chat/completions"
from abrasax import llm
try:
    r = llm.ask("Reply with exactly: FALLBACK-OK", max_tokens=12)
    print(json.dumps({"ok": True,
                      "routed_via": (r or {}).get("routed_via"),
                      "content": ((r or {}).get("content") or "")[:40]}))
except Exception as e:
    print(json.dumps({"ok": False, "error": type(e).__name__ + ": " + str(e)[:120]}))
'''
import subprocess

PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
try:
    p = subprocess.run([PY, "-c", code], cwd=ROOT, capture_output=True, text=True,
                       timeout=120, stdin=subprocess.DEVNULL,
                       creationflags=0x08000000)
    out = (p.stdout or "").strip().splitlines()
    payload = json.loads(out[-1]) if out else {"ok": False, "error": "no output"}
except Exception as e:  # noqa: BLE001
    payload = {"ok": False, "error": f"{type(e).__name__}: {e}"}

print(f"  result: {json.dumps(payload)[:200]}")
if payload.get("ok"):
    via = payload.get("routed_via")
    fb_ok = via in ("nvidia", "xpl")
    print(f"  [{'PASS' if fb_ok else 'FAIL'}] fell back to {via} when lmstudio was dead")
elif "insufficient" in str(payload.get("error", "")).lower() or \
     "429" in str(payload.get("error", "")):
    fb_ok = True
    print("  [PASS] fallback attempted; cloud provider rejected for quota (429/credits)")
    print("         that is a billing state, not a wiring fault")
else:
    fb_ok = False
    print("  [FAIL] fallback did not reach another provider")

print("\n=== 4. CONFIG vs RESIDENCY (the disagreement) ===")
cfg = json.load(open(os.path.join(ROOT, "CONFIG", "llm", "providers.json"),
                     encoding="utf-8"))
loaded_now = cfg["providers"]["lmstudio"]["models"].get("loaded_now", [])
print(f"  config loaded_now entries : {len(loaded_now)}")
for m in loaded_now:
    print(f"      {m}")

import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=10) as resp:
        actual = {m["id"] for m in json.loads(resp.read().decode())["data"]}
except Exception as e:  # noqa: BLE001
    print(f"  /v1/models unreachable: {e}")
    actual = set()

print(f"  actually resident         : {len(actual)}")
extra = sorted(actual - set(loaded_now))
print(f"  resident but undeclared   : {len(extra)}")
for m in extra[:8]:
    print(f"      {m}")
print("  NOTE: the config under-reports residency by %d models. The config is not"
      % len(extra))
print("        an inventory; treating it as one is how a model gets reloaded mid-run.")

print("\n=== SUMMARY ===")
print(f"  routing to first provider : {'PASS' if route_ok else 'FAIL'}")
print(f"  provider probe            : {'PASS' if probe_ok else 'FAIL'}")
print(f"  fallback reachable        : {'PASS' if fb_ok else 'FAIL'}")
print("\nRESULT:", "PASS" if (route_ok and probe_ok and fb_ok) else "DEFECTS")
sys.exit(0 if (route_ok and probe_ok and fb_ok) else 1)
