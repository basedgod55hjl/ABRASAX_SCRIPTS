"""Why do nemotron-3-nano-4b and the two deepseek models fail to answer?

Collected so far:
    nemotron   HTTP 400 "Engine protocol startup was aborted"  <- LM Studio refuses
    deepseek   HTTP 500 "Internal Server Error"               <- different failure
    log        contains NO load-failure lines; only /v1/models response bodies
    resident   only 2 llama-server processes: lfm2.5-1.2b and bonsai-27b

So 10 of the 12 "listed" models have no server backing them, and two of the five the
directive names cannot start. The most likely causes, in order:

  a  the GGUF file is absent or partial (LM Studio lists a model whose file moved)
  b  the quant needs more VRAM than is free (measured: 491 MiB free)
  c  the engine protocol genuine crash for this build

Check (a) first because it is decisive and cheap: locate each failing model's file
and verify its size against the header's expectation. Then check (b) arithmetically.
"""
import json
import os
import glob
import subprocess
import sys

HOME = os.path.expanduser("~")
MODELS_ROOT = os.path.join(HOME, ".lmstudio", "models")
CREATE_NO_WINDOW = 0x08000000

TARGETS = {
    "nvidia/nemotron-3-nano-4b": ["nemotron"],
    "deepseek/deepseek-r1-0528-qwen3-8b": ["deepseek-r1", "deepseek_r1"],
    "huihui-deepseek-v4-flash-abliterated-ds4": ["deepseek-v4", "huihui-deepseek"],
}

print("=== model files under ~/.lmstudio/models ===")
all_gguf = []
for dp, dn, fns in os.walk(MODELS_ROOT):
    for fn in fns:
        if fn.lower().endswith(".gguf"):
            all_gguf.append(os.path.join(dp, fn))
print(f"  {len(all_gguf)} .gguf file(s) total\n")

for i, p in enumerate(sorted(all_gguf), 1):
    try:
        mb = os.path.getsize(p) / (1024 * 1024)
    except OSError:
        mb = -1
    print(f"  {i:2d}. {mb:9.1f} MB  {os.path.relpath(p, MODELS_ROOT)}")

print("\n=== per target ===")
for model, needles in TARGETS.items():
    print("=" * 76)
    print(f"{model}")
    print("=" * 76)
    matches = []
    for p in all_gguf:
        low = p.lower()
        if any(n in low for n in needles):
            matches.append(p)
    if not matches:
        print("  NO FILE FOUND matching", needles)
        print("  -> LM Studio lists a model whose weights are not on disk.")
        print("     That alone explains a load failure.")
        continue
    for p in matches:
        size = os.path.getsize(p)
        mb = size / (1024 * 1024)
        # read the GGUF header to confirm it is not truncated
        try:
            with open(p, "rb") as f:
                magic = f.read(4)
                version = int.from_bytes(f.read(4), "little")
        except OSError as e:
            print(f"  {mb:8.1f} MB  {os.path.basename(p)}  READ ERROR {e}")
            continue
        ok_magic = magic == b"GGUF"
        print(f"  {mb:8.1f} MB  {os.path.basename(p)}")
        print(f"            magic={magic!r} ok={ok_magic} gguf_version={version}")
        if mb < 100:
            print("            WARNING: under 100 MB -- almost certainly a "
                  "partial/placeholder download")

print("\n=== VRAM arithmetic ===")
try:
    q = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=20,
        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    tot, used, free = [int(x) for x in q.stdout.strip().split(",")]
    print(f"  total {tot} MiB   used {used} MiB   free {free} MiB")
    # rough Q4_K_M rule: 0.6 GB per billion params, plus ~0.5 GB context overhead
    print("\n  rough feasibility for a 4B Q4 model on the remaining VRAM:")
    est = int(4 * 600 + 500)
    print(f"    4B Q4 estimate ~{est} MiB vs {free} MiB free "
          f"-> {'FITS' if est <= free else 'DOES NOT FIT'}")
except Exception as e:  # noqa: BLE001
    print(f"  nvidia-smi failed: {e}")

print("\n=== resident servers ===")
try:
    q = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like '%llama%'\" | "
         "ForEach-Object { \"{0}|{1}\" -f $_.ProcessId,(Get-Process -Id $_.ProcessId -EA 0).WorkingSet64 }"],
        capture_output=True, text=True, timeout=60,
        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    rows = [ln for ln in q.stdout.strip().splitlines() if "|" in ln]
    print(f"  {len(rows)} llama-server process(es)")
    for ln in rows:
        pid, ws = ln.split("|")
        print(f"    pid={pid:8s} {int(ws)//(1024*1024):6d} MB")
    print(f"\n  12 models listed but {len(rows)} server process(es): the rest are")
    print("  JIT-load candidates, not resident runners.")
except Exception as e:  # noqa: BLE001
    print(f"  {e}")

sys.exit(0)
