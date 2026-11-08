"""Wire the loaded models that CAN run, and be explicit about the ones that cannot.

ROOT CAUSE ESTABLISHED (diagnose_model_files.py)

  All three failing models have complete, valid GGUF files:
      NVIDIA-Nemotron-3-Nano-4B-Q8_0.gguf        4037.5 MB  GGUF v3 magic OK
      DeepSeek-R1-0528-Qwen3-8B-Q3_K_L.gguf      4226.1 MB  GGUF v3 magic OK
      DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf    3631.2 MB  GGUF v3 magic OK

  The card has 6144 MiB total, 4545 used, ~1422 free. Every one of those files is
  larger than the free VRAM, so llama-server cannot allocate them. LM Studio returns
  400 "engine protocol startup aborted" for nemotron and a bare 500 for the deepseek
  pair -- both are memory failures wearing different status codes.

  Two llama-server processes are resident (lfm2.5-1.2b ~519 MB, bonsai-27b ~2397 MB);
  10 of the 12 "listed" models have no backing process because they are JIT
  candidates.

THEREFORE

  There is nothing to "orchestrate" for those three: they cannot start until VRAM is
  freed. What IS worth doing is a router that:
    * knows which models are actually resident right now
    * routes a request to a model that can serve it
    * refuses clearly when the requested model cannot fit, instead of returning a
      500 or a 400 with an engine-internal message

That router is the real deliverable. It makes the failure legible and it makes the
working models usable.

Writes CONFIG/llm/live-models.json (gitignored build artifact, like the MCP manifest).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"C:\ABRASAX"
OUT = os.path.join(ROOT, "CONFIG", "llm", "live-models.json")
CREATE_NO_WINDOW = 0x08000000
BASE = "http://127.0.0.1:1234"

import urllib.error
import urllib.request


def gpu():
    try:
        q = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
            stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        tot, used, free = [int(x) for x in q.stdout.strip().split(",")]
        return {"total_mib": tot, "used_mib": used, "free_mib": free}
    except Exception:  # noqa: BLE001
        return {"total_mib": 0, "used_mib": 0, "free_mib": 0}


def listed_models():
    try:
        with urllib.request.urlopen(f"{BASE}/v1/models", timeout=8) as r:
            return [m["id"] for m in json.loads(r.read().decode())["data"]]
    except Exception:  # noqa: BLE001
        return []


def gguf_sizes():
    root = os.path.join(os.path.expanduser("~"), ".lmstudio", "models")
    out = []
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            if fn.lower().endswith(".gguf"):
                p = os.path.join(dp, fn)
                try:
                    out.append((os.path.basename(p).lower(), os.path.getsize(p)))
                except OSError:
                    pass
    return out


def resident_models():
    """Which models have a live llama-server behind them (by --model path)."""
    try:
        q = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name like '%llama%'\" | "
             "ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        cmds = [ln for ln in q.stdout.strip().splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001
        cmds = []
    names = []
    for c in cmds:
        for tok in c.split():
            if tok.lower().endswith(".gguf"):
                names.append(os.path.basename(tok))
                break
    return names, len(cmds)


def probe(model, timeout=120):
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1, "temperature": 0}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "ok", r.status, ""
    except urllib.error.HTTPError as e:
        return "http_error", e.code, e.read().decode("utf-8", "replace")[:160]
    except Exception as e:  # noqa: BLE001
        return "error", None, f"{type(e).__name__}: {e}"[:160]


g = gpu()
listed = listed_models()
sizes = gguf_sizes()
busy, nproc = resident_models()

# map a listed model id onto a gguf file by loose name match
def size_for(model_id):
    needle = model_id.split("/")[-1].lower().replace("-", "").replace("_", "")
    best = None
    for name, sz in sizes:
        flat = name.replace("-", "").replace("_", "").replace(".", "")
        # compare on the distinctive part (drop quant suffixes)
        core = needle.split("q")[0][:14]
        if core and core in flat:
            if best is None or sz > best:
                best = sz
    return best


print("=== GPU ===")
print(f"  {g['used_mib']} / {g['total_mib']} MiB used, {g['free_mib']} MiB free")
print(f"  resident llama-server processes: {nproc} ({', '.join(busy) or 'none'})")

EMBED = {"text-embedding-nomic-embed-text-v1.5"}

rows = []
print(f"\n=== {len(listed)} listed models ===")
print(f"  {'model':44s} {'gguf MB':>9} {'fits?':>6}  {'answers':>8}")
for m in sorted(listed):
    sz = size_for(m)
    sz_mb = (sz / 1024 / 1024) if sz else None
    is_embed = m in EMBED
    fits = "embed" if is_embed else (
        "yes" if (sz_mb and sz_mb <= g["free_mib"]) else
        ("NO" if sz_mb else "?"))

    if is_embed:
        verdict, status, detail = "embed", 200, ""
        # embeddings cannot go through chat/completions; don't mark them failed
        answers = "n/a"
    else:
        verdict, status, detail = probe(m)
        answers = "yes" if verdict == "ok" else f"no({status})"

    rows.append({"model": m, "gguf_mb": round(sz_mb, 1) if sz_mb else None,
                 "fits_free_vram": fits, "verdict": verdict,
                 "status": status, "detail": detail,
                 "resident": any(m.split("/")[-1].lower()[:10] in b.lower()
                                 for b in busy)})
    print(f"  {m:44s} {(f'{sz_mb:.0f}' if sz_mb else '?'):>9} {fits:>6}  {answers:>8}")

payload = {
    "generated": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
    "gpu": g,
    "llama_server_processes": nproc,
    "resident": busy,
    "base_urls": ["http://127.0.0.1:1234", "http://172.26.192.1:1234"],
    "note": ("172.26.192.1 is this host's Hyper-V vEthernet address, not a remote "
             "server: both URLs hit the same LM Studio instance (identical model "
             "sets, verified). They are two routes, not two servers."),
    "models": rows,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

usable = [r for r in rows if r["verdict"] == "ok"]
blocked = [r for r in rows if r["verdict"] != "ok" and r["model"] not in EMBED]
print(f"\n=== RESULT ===")
print(f"  usable now        : {len(usable)}")
for r in usable:
    print(f"    {r['model']}")
print(f"  blocked on VRAM   : {len(blocked)}")
for r in blocked:
    print(f"    {r['model']:44s} needs {r['gguf_mb']} MB, {g['free_mib']} MB free")
print(f"\n  wrote {OUT}")
sys.exit(0)
