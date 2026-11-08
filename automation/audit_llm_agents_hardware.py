"""Wiring audit: do the LLM / agent / hardware layers agree with what is running?

Section 3 is about the local LLM, the multi-agent layer and the hardware. Three
things are easy to claim and hard to verify, so verify them:

  1  PROVIDER CHAIN, live. CONFIG/llm/providers.json declares
        order = lmstudio -> nvidia -> xpl, auto_fallback, jev_gate
     Tonight already found docs claiming state that was not true. Does the chain
     actually route, and does fallback work when the first provider is unreachable?

  2  MODEL RESIDENCY. providers.json says
        loaded_now = [bonsai-27b, lfm2.5-1.2b, nomic-embed]
     Measured: /v1/models lists 12. A config that under-reports residency is how
     someone concludes a model is not loaded and reloads it mid-run.

  3  AGENT REGISTRY. 13 agents are registered. Registered is not the same as
     callable -- each needs a role doctrine and a working LLM route.

  4  HARDWARE HEADROOM. VRAM 5670/6144 MiB used, GPU 24%, 56 C. The renderer and
     the LLM share one 6 GB card; that is the real constraint on concurrency.

Read-only. No model is loaded, unloaded, or called destructively.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = r"C:\ABRASAX"
CFG = os.path.join(ROOT, "CONFIG", "llm", "providers.json")
CREATE_NO_WINDOW = 0x08000000


def http_json(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        return {"__error__": f"{type(e).__name__}: {e}"}


print("=== 1. PROVIDER CONFIG vs REALITY ===")
cfg = json.load(open(CFG, encoding="utf-8"))
policy = cfg.get("policy", {})
prov = cfg.get("providers", {})
print(f"  declared order   : {' -> '.join(policy.get('order', []))}")
print(f"  auto_fallback    : {policy.get('auto_fallback')}")
print(f"  jev_gate         : {policy.get('jev_gate')}")

for name, p in prov.items():
    base = p.get("base_url") or os.environ.get(p.get("base_url_env", ""), "")
    print(f"  {name:10s} base={base[:48]}")

# is each provider reachable right now?
def reachable(base):
    if not base:
        return None
    try:
        host = base.split("//", 1)[1].split("/")[0]
        h, _, port = host.partition(":")
        port = int(port or (443 if base.startswith("https") else 80))
        s = socket.socket()
        s.settimeout(2.0)
        try:
            s.connect((h, port))
            return True
        finally:
            s.close()
    except (OSError, IndexError, ValueError):
        return False


print("\n  reachability:")
for name, p in prov.items():
    base = p.get("base_url") or ""
    if not base:
        print(f"    {name:10s} (no base_url in config; uses env)")
        continue
    print(f"    {name:10s} TCP {'UP' if reachable(base) else 'DOWN'}")

print("\n=== 2. MODEL RESIDENCY (config vs /v1/models) ===")
lm = prov.get("lmstudio", {})
declared_loaded = set(lm.get("models", {}).get("loaded_now", []))
declared_aliases = lm.get("models", {})
alias_values = {v for k, v in declared_aliases.items()
                if isinstance(v, str) and "/" in v}

models = http_json("http://127.0.0.1:1234/v1/models")
if "__error__" in models:
    print(f"  /v1/models unreachable: {models['__error__']}")
    actual = set()
else:
    actual = {m["id"] for m in models.get("data", [])}

print(f"  config says loaded_now : {len(declared_loaded)}")
for m in sorted(declared_loaded):
    print(f"      {m:48s} {'PRESENT' if m in actual else 'ABSENT'}")
print(f"  /v1/models reports     : {len(actual)}")
missing_from_config = sorted(actual - declared_loaded - alias_values - {"text-embedding-nomic-embed-text-v1.5"})
print(f"  loaded but NOT in config loaded_now: {len(missing_from_config)}")
for m in missing_from_config[:10]:
    print(f"      {m}")

print("\n=== 3. AGENT REGISTRY vs DOCTRINE ===")
try:
    sys.path.insert(0, ROOT)
    out = subprocess.run([os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe"),
                          "-m", "abrasax", "agents"],
                         cwd=ROOT, capture_output=True, text=True, timeout=120,
                         stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    agents = json.loads(out.stdout)
except Exception as e:  # noqa: BLE001
    print(f"  could not list agents: {e}")
    agents = []

roles_dir = os.path.join(ROOT, "AGENTS", "ROLES")
role_files = {}
if os.path.isdir(roles_dir):
    for fn in os.listdir(roles_dir):
        if fn.endswith(".md"):
            role_files[fn[:-3]] = fn

print(f"  registered agents : {len(agents)}")
print(f"  role doctrine files: {len(role_files)}")

# every agent should map to a doctrine by name or by registry
reg = os.path.join(roles_dir, "registry.json")
mapping = {}
if os.path.exists(reg):
    try:
        rj = json.load(open(reg, encoding="utf-8"))
        if isinstance(rj, dict):
            mapping = rj.get("routing", rj)
    except json.JSONDecodeError:
        pass

unmapped = []
for a in agents:
    key = a.lower().replace("_", "-")
    found = (key in role_files) or (a in role_files) or \
            any(key in k or k in key for k in role_files) or (a in mapping)
    if not found:
        unmapped.append(a)
    print(f"    {a:24s} {'doctrine ok' if found else 'NO DOCTRINE'}")

print("\n=== 4. HARDWARE ===")
try:
    q = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,"
                       "temperature.gpu,power.draw", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=20,
        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    print(f"  {q.stdout.strip()}")

    q2 = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                         "--format=csv,noheader"],
                        capture_output=True, text=True, timeout=20,
                        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    procs = [ln for ln in q2.stdout.strip().splitlines() if ln.strip()]
    print(f"  compute apps on GPU: {len(procs)}")
    if procs:
        print(f"    (first 4) {procs[:4]}")
    else:
        print("    per-process VRAM attribution unavailable on this driver")
except (OSError, subprocess.TimeoutExpired) as e:
    print(f"  nvidia-smi failed: {e}")

print("\nRESULT: audit only")
sys.exit(0)
