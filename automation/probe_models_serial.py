"""The 12-way concurrent probe lied. Retest serially, one model at a time.

WHAT WENT WRONG IN wire_live_models.py

  It probed 12 models in a loop with no delay. Even the two models that HAVE a live
  llama-server behind them (liquid/lfm2.5-1.2b, prism-ml/bonsai-27b) came back 500.
  That is not a VRAM problem -- those servers are already loaded and resident.

  Cause: LM Studio serialises model work. Twelve back-to-back requests, several of
  which trigger JIT loads that each try to allocate a multi-GB model, saturate the
  queue; the in-flight ones then error out with 500. My own probe induced the
  failure I then reported as a system defect.

  This is the same class of error as every other check tonight: the instrument
  changed the thing it was measuring.

CORRECT METHOD

  * strictly serial, with a settle delay between requests
  * long timeout per request (a JIT load of a large model can take minutes)
  * record wall time, so a genuinely slow load is distinguishable from a crash
  * probe the two KNOWN-RESIDENT models first, to establish a baseline that works
"""
import json
import os
import subprocess
import time

BASE = "http://127.0.0.1:1234"
CREATE_NO_WINDOW = 0x08000000
SETTLE_S = 3.0

import urllib.error
import urllib.request


def gpu_free():
    try:
        q = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
            stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        return int(q.stdout.strip())
    except Exception:  # noqa: BLE001
        return -1


def probe(model, timeout=240):
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1, "temperature": 0}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return "ok", r.status, round(time.time() - t0, 1), ""
    except urllib.error.HTTPError as e:
        return "http_error", e.code, round(time.time() - t0, 1), \
               e.read().decode("utf-8", "replace")[:120]
    except Exception as e:  # noqa: BLE001
        return "error", None, round(time.time() - t0, 1), f"{type(e).__name__}"[:80]


def listed():
    try:
        with urllib.request.urlopen(f"{BASE}/v1/models", timeout=10) as r:
            return [m["id"] for m in json.loads(r.read().decode())["data"]]
    except Exception:  # noqa: BLE001
        return []


# the two with confirmed resident servers, in that order
RESIDENT_FIRST = ["liquid/lfm2.5-1.2b", "prism-ml/bonsai-27b"]

models = listed()
ordered = [m for m in RESIDENT_FIRST if m in models]
ordered += [m for m in sorted(models) if m not in ordered]

print(f"=== SERIAL PROBE of {len(ordered)} model(s) ===")
print(f"  free VRAM at start: {gpu_free()} MiB\n")
print(f"  {'model':44s} {'verdict':10s} {'http':>5} {'secs':>6}  free_vram")

results = []
for m in ordered:
    if "embed" in m.lower():
        print(f"  {m:44s} {'skip':10s} {'-':>5} {'-':>6}  (embedding model)")
        results.append({"model": m, "verdict": "embedding"})
        continue

    verdict, status, secs, detail = probe(m)
    print(f"  {m:44s} {verdict:10s} {str(status):>5} {secs:>6}  {gpu_free()} MiB"
          + (f"   {detail}" if detail else ""))
    results.append({"model": m, "verdict": verdict, "status": status,
                    "secs": secs, "detail": detail})
    time.sleep(SETTLE_S)

print("\n=== SUMMARY ===")
ok = [r for r in results if r.get("verdict") == "ok"]
print(f"  answered : {len(ok)}/{len([r for r in results if r.get('verdict') != 'embedding'])}")
for r in ok:
    print(f"    {r['model']}  ({r['secs']}s)")

failed = [r for r in results if r.get("verdict") in ("http_error", "error")]
if failed:
    print(f"  failed  : {len(failed)}")
    for r in failed:
        print(f"    {r['model']:44s} {r['verdict']} {r.get('status')} {r.get('detail','')[:60]}")

out = r"C:\ABRASAX\LOGS\serial-model-probe.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "serial": True, "results": results}, f, indent=2)
print(f"\n  wrote {out}")
