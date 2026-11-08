"""Get the FULL error for the models that fail to load.

Three failures, each truncated by my own probe:
    nvidia/nemotron-3-nano-4b          HTTP 400 "Failed to loa..."
    deepseek/deepseek-r1-0528-qwen3-8b HTTP 500 <!DOCTYPE html...
    huihui-deepseek-v4-flash-...-ds4   HTTP 500 <!DOCTYPE html...

The 400 is LM Studio saying it cannot load the model. The 500 with an HTML body is
almost certainly a stack trace page from the llama-server child process, which is a
different failure: the server crashed rather than refused.

Never print a truncated error again -- that habit cost four wrong conclusions in the
previous section.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = r"C:\ABRASAX"
BASE = "http://127.0.0.1:1234"
CREATE_NO_WINDOW = 0x08000000

TARGETS = [
    "nvidia/nemotron-3-nano-4b",
    "deepseek/deepseek-r1-0528-qwen3-8b",
    "huihui-deepseek-v4-flash-abliterated-ds4",
]


def probe_chat(model, max_tokens=1, timeout=180):
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": max_tokens, "temperature": 0}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


for m in TARGETS:
    print("=" * 78)
    print(f"MODEL: {m}")
    print("=" * 78)
    status, body = probe_chat(m)
    print(f"  status: {status}")
    print(f"  body length: {len(body)} chars")

    if body.lstrip().startswith("<"):
        # HTML error page -- extract the visible text
        import re
        text = re.sub(r"<[^>]+>", " ", body)
        text = re.sub(r"\s+", " ", text).strip()
        print(f"  HTML error page, visible text:")
        for i in range(0, min(len(text), 700), 96):
            print("    " + text[i:i + 96])
        # look for a llama-server style error
        for marker in ("error", "Error", "failed", "cannot", "out of memory",
                       "OOM", "insufficient", "too large"):
            if marker in text:
                idx = text.find(marker)
                print(f"  ...near '{marker}': {text[max(0,idx-60):idx+140]}")
                break
    else:
        # JSON error or success
        try:
            d = json.loads(body)
            print(f"  parsed JSON: {json.dumps(d)[:600]}")
        except json.JSONDecodeError:
            print(f"  raw: {body[:600]}")
    print()

print("=" * 78)
print("LLAMA-SERVER STDERR")
print("=" * 78)
try:
    q = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like '%llama%'\" | "
         "ForEach-Object { \"{0}|{1}\" -f $_.ProcessId, $_.CommandLine }"],
        capture_output=True, text=True, timeout=60,
        stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    for ln in q.stdout.strip().splitlines()[:4]:
        print("  " + ln[:170])
except Exception as e:  # noqa: BLE001
    print(f"  {e}")

print("\nRESULT: full errors captured")
sys.exit(0)
