"""Probe each local GGUF directly against a throwaway llama-server we control.

Fix over v1: the server opens its socket BEFORE the model finishes loading, so a
bare TCP connect is not readiness. v1 therefore got 503 "Loading model" for every
model. This version polls GET /health until it reports ok, which is the real
readiness signal (llama.cpp /health returns 503 until weights are resident).

Usage: python probe_models.py [name ...]
"""
import json, os, socket, subprocess, sys, time, urllib.error, urllib.request

LLAMA = r"C:\abrasax\BUILD\llamacpp\build\bin\llama-server.exe"
MODELS = r"C:\Users\lucar\.lmstudio\models"
LOGDIR = r"C:\ABRASAX\logs"

CANDIDATES = [
    ("LFM2.5-1.2B-Q6_K", os.path.join(MODELS,
     r"lmstudio-community\LFM2.5-1.2B-Instruct-GGUF\LFM2.5-1.2B-Instruct-Q6_K.gguf")),
    ("LFM2.5-1.2B-Q8_0", os.path.join(MODELS,
     r"lmstudio-community\LFM2.5-1.2B-Instruct-GGUF\LFM2.5-1.2B-Instruct-Q8_0.gguf")),
    ("OrcaCyber-Q8_0", os.path.join(MODELS,
     r"OrcaCyber\OrcaCyber-Nano-1.0-AI-Defense\OrcaCyber-Nano-1.0-AI-Defense-Q8_0.gguf")),
    ("OrcaCyber-DFlash2-Q8_0", os.path.join(MODELS,
     r"OrcaCyber\OrcaCyber-Nano-1.0-AI-Defense\OrcaCyber-Nano-1.0-AI-Defense-DFlash2-Q8_0.gguf")),
    ("Gemma-4-E2B-Q2_K_P", os.path.join(MODELS,
     r"HauhauCS\Gemma-4-E2B-Uncensored-HauhauCS-Aggressive\Gemma-4-E2B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf")),
    ("Qwen3-VL-4B-Q8_0", os.path.join(MODELS,
     r"prithivMLmods\Qwen3-VL-4B-Instruct-Unredacted-MAX-GGUF\Qwen3-VL-4B-Instruct-Unredacted-MAX.Q8_0.gguf")),
    ("DeepSeek-R1-8B-Q3_K_L", os.path.join(MODELS,
     r"lmstudio-community\DeepSeek-R1-0528-Qwen3-8B-GGUF\DeepSeek-R1-0528-Qwen3-8B-Q3_K_L.gguf")),
]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_healthy(port, timeout=240):
    """llama.cpp /health returns 503 until weights are loaded, then 200 ok."""
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=3) as r:
                if r.status == 200:
                    return True, round(time.time() - t0, 1)
        except urllib.error.HTTPError as e:
            last = e.code
        except Exception as e:
            last = type(e).__name__
        time.sleep(1.0)
    return False, (round(time.time() - t0, 1), last)


def chat(port, timeout=120):
    body = json.dumps({"model": "x",
                       "messages": [{"role": "user", "content": "Say PONG"}],
                       "max_tokens": 16, "temperature": 0}).encode()
    r = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % port,
                               data=body, method="POST")
    r.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            b = json.loads(resp.read().decode())
        ch = b["choices"][0]
        return (resp.status, (ch["message"].get("content") or "").strip(),
                ch.get("finish_reason"),
                b.get("timings", {}).get("predicted_per_second"), time.time() - t0)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:80], None, None, time.time() - t0
    except Exception as e:
        return None, type(e).__name__, None, None, time.time() - t0


def probe(name, path):
    if not os.path.exists(path):
        return {"name": name, "status": "missing"}
    port = free_port()
    logpath = os.path.join(LOGDIR, "probe_%s.log" % name.replace("/", "_"))
    log = open(logpath, "ab")
    proc = subprocess.Popen(
        [LLAMA, "--model", path, "--port", str(port), "--host", "127.0.0.1",
         "-ngl", "99", "-c", "2048", "--no-webui"],
        stdout=log, stderr=log, stdin=subprocess.DEVNULL,
        creationflags=0x08000000)
    try:
        ready, info = wait_healthy(port)
        if not ready:
            return {"name": name, "status": "load-failed", "waited": info}
        st, content, fin, tps, dt = chat(port)
        return {"name": name, "status": st, "finish": fin,
                "content": (content or "")[:40],
                "tps": round(tps, 1) if tps else None,
                "seconds": round(dt, 2), "load_s": info}
    finally:
        proc.kill()
        try:
            proc.wait(10)
        except Exception:
            pass
        log.close()
        time.sleep(2.0)


wanted = sys.argv[1:]
results = []
for name, path in CANDIDATES:
    if wanted and name not in wanted:
        continue
    r = probe(name, path)
    results.append(r)
    print(json.dumps(r), flush=True)

if not wanted:
    json.dump(results, open(os.path.join(LOGDIR, "model_probe.json"), "w"), indent=2)
    print("\nwrote logs/model_probe.json")
