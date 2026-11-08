"""mesh_runner — probe every AI endpoint and write one truthful status log.

Every endpoint is asked to produce a REAL answer. A 200 with an empty body is
recorded as unusable, because that exact false-success was measured on this box
(a reasoning model spent its whole budget on reasoning_content and returned no
content while the HTTP status said 200).

Run: python SCRIPTS/automation/mesh_runner.py [--render-only]
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = r"C:\ABRASAX"
sys.path.insert(0, ROOT)

from abrasax import mesh_log  # noqa: E402


def load_env() -> dict:
    env = {}
    try:
        for line in io.open(os.path.join(ROOT, ".env"), encoding="utf-8", errors="replace"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, _, v = s.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def chat_payload(model: str, prompt: str = "Reply with the single word: PONG") -> dict:
    return {"model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512, "temperature": 0}


def main() -> int:
    env = load_env()

    if "--render-only" in sys.argv:
        print(mesh_log.render())
        return 0

    # ---- local inference we control -------------------------------------
    mesh_log.probe_http(
        "llamacpp-local:8083",
        "http://127.0.0.1:8083/v1/chat/completions",
        payload=chat_payload("LFM2.5-1.2B-Instruct-Q6_K.gguf"), timeout=90)

    # ---- abrasax gateway ------------------------------------------------
    for model in ("LFM2.5-1.2B-Instruct-Q6_K.gguf", "deepseek", "deepseek-flash"):
        mesh_log.probe_http(
            "gateway:9001/%s" % model,
            "http://127.0.0.1:9001/v1/chat/completions",
            payload=chat_payload(model), timeout=90)

    # ---- LM Studio (catalogue may be broader than capability) -----------
    mesh_log.probe_http(
        "lmstudio:1234",
        "http://127.0.0.1:1234/v1/chat/completions",
        payload=chat_payload("deepseek/deepseek-r1-0528-qwen3-8b"), timeout=120)

    # ---- DeepSeek -------------------------------------------------------
    dsk = env.get("DEEPSEEK_API_KEY")
    if dsk:
        base = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        mesh_log.probe_http(
            "deepseek:api", base + "/chat/completions",
            headers={"Authorization": "Bearer " + dsk},
            payload=chat_payload("deepseek-flash"), timeout=60)
    else:
        mesh_log.blocker("deepseek:api", "no DEEPSEEK_API_KEY in .env")

    # ---- NVIDIA (both keys) --------------------------------------------
    nv_base = env.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nv_model = env.get("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    for i in (1, 2):
        key = env.get("NVIDIA_API_KEY_%d" % i)
        if not key:
            mesh_log.blocker("nvidia:key%d" % i, "NVIDIA_API_KEY_%d missing" % i)
            continue
        mesh_log.probe_http(
            "nvidia:key%d" % i, nv_base + "/chat/completions",
            headers={"Authorization": "Bearer " + key},
            payload=chat_payload(nv_model), timeout=120)

    # ---- JEV (System One oracle) ---------------------------------------
    jk = env.get("JEV_API_KEY")
    if jk:
        jbase = env.get("JEV_BASE_URL", "https://api.typesafe.ai/v1").rstrip("/")
        state = "Patch raises the supervisor health timeout from 0.6s to 2.0s."
        jev = mesh_log.probe_http(
            "jev:systemone", jbase + "/systemone",
            headers={"Authorization": "Bearer " + jk},
            payload={"model": "jev-latest", "state": state,
                     "questions": {"safe": {"type": "noul",
                                            "instructions": "Is this patch safe?"}}},
            timeout=60, expect="json")
        if jev.get("ok"):
            mesh_log.record("note", "jev:systemone", detail="System One answered")
    else:
        mesh_log.blocker("jev:systemone", "no JEV_API_KEY in .env")

    # ---- GitHub ---------------------------------------------------------
    pat = (os.environ.get("ABRASAX_GH_PAT") or env.get("GITHUB_PAT")
           or env.get("GH_PAT") or env.get("GITHUB_TOKEN"))
    if pat:
        mesh_log.probe_http("github:api", "https://api.github.com/user",
                            headers={"Authorization": "Bearer " + pat,
                                     "Accept": "application/vnd.github+json",
                                     "User-Agent": "abrasax-mesh"},
                            timeout=30, expect="json")
    else:
        mesh_log.blocker("github:api", "no GitHub PAT in env")

    # ---- known blockers, measured (kept honest across runs) -------------
    mesh_log.blocker("lmstudio:model_pinner",
                     "model_pinner.py enforces a single pinned 8B and unloads every "
                     "other model ~every 60s, so no other LM Studio model can stay loaded",
                     "C:\\vlc-build\\model_pinner.py + C:\\vlc-build\\logs\\model_pinner.log")
    mesh_log.blocker("comfyui:8188", "no ComfyUI install on this host",
                     "C:\\abrasax\\TOOLS\\AI-ImageGen absent")
    mesh_log.blocker("imagegen:8199", "no ImageGen install on this host",
                     "C:\\abrasax\\TOOLS\\AI-ImageGen absent")

    text = mesh_log.render()
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
