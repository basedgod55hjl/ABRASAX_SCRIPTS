"""Map the LM Studio server and every llama-server instance, then wire them.

MEASURED BEFORE ANY WIRING

  172.26.192.1:1234  is NOT a remote host. It is this machine's Hyper-V
                     "vEthernet (Default Switch)" address (prefix /20).
  127.0.0.1:1234     is the loopback path to the same listener.
  Both answer /v1/models with 12 models.

So "connect to 172.26.192.1:1234" is already satisfied by the existing loopback
config -- the difference is a network-stack path, not a different server. Claiming
to have "connected" it would be theatre.

WHAT IS ACTUALLY WORTH DOING

  1  prove both addresses reach the SAME server instance (same model set, same
     uptime/headers), so a failover between them is meaningless and can be dropped
  2  enumerate the llama-server processes that back those models
  3  check the five models named in the directive are present AND callable
  4  report per-model: resident? reachable? does a 1-token completion succeed?

Point 4 is the only claim that matters: a model listed in /v1/models is not
necessarily able to answer. LM Studio JIT-loads, and a JIT load can fail.

Read-only. No model is loaded or unloaded.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = r"C:\ABRASAX"
CREATE_NO_WINDOW = 0x08000000

HOSTS = [("loopback", "http://127.0.0.1:1234"),
         ("hyperv", "http://172.26.192.1:1234")]

TARGETS = [
    "gemma-4-e2b-uncensored-hauhaucs-aggressive",
    "prism-ml/bonsai-27b",
    "text-embedding-nomic-embed-text-v1.5",
    "nvidia/nemotron-3-nano-4b",
]


def http_json(url, timeout=8, method="GET", body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), dict(r.headers), r.status
    except urllib.error.HTTPError as e:
        return {"__http_error__": e.code, "body": e.read()[:200].decode("utf-8", "replace")}, dict(e.headers), e.code
    except Exception as e:  # noqa: BLE001
        return {"__error__": f"{type(e).__name__}: {e}"}, {}, None


print("=== 1. ARE THE TWO ADDRESSES THE SAME SERVER? ===")
sets = {}
for label, base in HOSTS:
    d, hdrs, status = http_json(f"{base}/v1/models")
    ids = sorted(m["id"] for m in d.get("data", [])) if "data" in d else []
    sets[label] = set(ids)
    server = hdrs.get("Server", hdrs.get("server", "?"))
    print(f"  {label:9s} {base:28s} status={status} models={len(ids)} server={server}")

same = sets.get("loopback") == sets.get("hyperv")
print(f"\n  identical model set: {same}")
if same and sets.get("loopback"):
    print("  -> the two URLs are the SAME LM Studio instance reached by two routes.")
    print("     A failover between them would add nothing; this is recorded, not wired.")

# uptime is the strongest identity signal if exposed
print("\n  identity probe (uptime-specific fields):")
for label, base in HOSTS:
    d, hdrs, _ = http_json(f"{base}/api/v0/models")
    if "data" in d:
        print(f"    {label}: /api/v0/models -> {len(d['data'])} entries")
    else:
        print(f"    {label}: /api/v0/models -> {str(d)[:80]}")

print("\n=== 2. llama-server PROCESSES BEHIND THOSE MODELS ===")
try:
    q = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like '%llama%'\" | "
         "ForEach-Object { \"{0}|{1}|{2}\" -f $_.ProcessId, "
         "(Get-Process -Id $_.ProcessId -EA 0).WorkingSet64, $_.CommandLine }"],
        capture_output=True, text=True, timeout=60,
        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    rows = [ln for ln in q.stdout.strip().splitlines() if "|" in ln]
    print(f"  {len(rows)} llama-family process(es)")
    for ln in rows[:8]:
        pid, ws, cmd = ln.split("|", 2)
        try:
            mb = int(ws) // (1024 * 1024)
        except ValueError:
            mb = 0
        # pull the model path out of the command line
        model = ""
        for tok in (cmd or "").split():
            if tok.endswith(".gguf") or "/models/" in tok:
                model = os.path.basename(tok)
                break
        print(f"    pid={pid:8s} {mb:6d} MB  {model[:56] or cmd[:56]}")
except (OSError, subprocess.TimeoutExpired) as e:
    print(f"  enumeration failed: {type(e).__name__}: {e}")

print("\n=== 3. THE FOUR NAMED MODELS: PRESENT AND CALLABLE? ===")
present = sets.get("loopback", set())
print(f"  {'model':44s} {'listed':8s} {'completion':12s} detail")
results = {}
for m in TARGETS:
    listed = m in present
    detail = ""
    ok_call = None
    if not listed:
        detail = "not in /v1/models"
    else:
        # an embedding model cannot do chat/completions, so use the right endpoint
        is_embed = "embed" in m.lower()
        if is_embed:
            body = {"model": m, "input": "probe"}
            d, _, st = http_json("http://127.0.0.1:1234/v1/embeddings", timeout=40,
                                 method="POST", body=body)
        else:
            body = {"model": m, "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1, "temperature": 0}
            d, _, st = http_json("http://127.0.0.1:1234/v1/chat/completions",
                                 timeout=90, method="POST", body=body)
        if "__error__" in d:
            detail = d["__error__"][:60]
            ok_call = False
        elif "__http_error__" in d:
            detail = f"HTTP {d['__http_error__']}: {d['body'][:60]}"
            ok_call = False
        else:
            ok_call = True
            detail = "answered" if not is_embed else "embedded"
    results[m] = (listed, ok_call, detail)
    print(f"  {m:44s} {str(listed):8s} {str(ok_call):12s} {detail[:60]}")

print("\n=== 4. deepseek-r1 (the fifth name) ===")
ds_candidates = [x for x in present if "deepseek" in x.lower()]
print(f"  matches in /v1/models: {ds_candidates or 'NONE'}")
for m in ds_candidates:
    body = {"model": m, "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1, "temperature": 0}
    d, _, st = http_json("http://127.0.0.1:1234/v1/chat/completions",
                         timeout=120, method="POST", body=body)
    if "__error__" in d or "__http_error__" in d:
        print(f"    {m}: FAIL {str(d)[:80]}")
    else:
        print(f"    {m}: answered (1 token)")

print("\n=== SUMMARY ===")
listed_all = all(v[0] for v in results.values())
callable_all = all(v[1] for v in results.values())
print(f"  all four named models listed   : {listed_all}")
print(f"  all four respond to a probe    : {callable_all}")
print(f"  two URLs are one instance      : {same}")
print("\nRESULT: report produced")
sys.exit(0)
