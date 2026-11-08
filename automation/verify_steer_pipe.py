"""Prove ui_steer's plumbing end-to-end using a model that is already resident.

The Unity/vision GGUFs can't load while VRAM is saturated, but the *plumbing*
(capture -> image encode -> chat -> ledger -> /activity -> overlay) must be
provable now, not later. This drives the same functions in ui_steer.py with
nvidia/nemotron-3-nano-4b, which LM Studio already has loaded.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
spec = importlib.util.spec_from_file_location(
    "ui_steer", ROOT / "ENGINE/floating_brain/ui_steer.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)  # type: ignore[union-attr]

img = ROOT / "LOGS/overlay_live.png"
print("frame:", img.exists(), img.stat().st_size if img.exists() else 0)

b64, dims = ui.b64_image(img)
print(f"encoded base64 chars={len(b64)} dims={dims}")

# 1. text-only round trip on a resident model
out = ui.chat("nvidia/nemotron-3-nano-4b",
              "In one short line: what does a well-designed status HUD need?",
              timeout=180, max_tokens=200)
print(f"chat ok={bool(out['text'])} tokens={out['tokens']} "
      f"tok/s={out['tokens_per_s']} latency={out['latency_s']}s")
print("reply:", out["text"][:200].replace("\n", " "))

# 2. vision request to a NON-resident VL model -- must fail cleanly, not hang
v, attempts = ui.first_working(
    ui.VISION_MODELS,
    lambda m: ui.chat(m, [{"type": "text", "text": "Describe this HUD."},
                          {"type": "image_url",
                           "image_url": {"url": f"data:image/png;base64,{b64}"}}],
                      timeout=90, max_tokens=60))
print("vision result:", "OK" if v else "unavailable (expected while VRAM is full)")
for a in attempts:
    print("  attempt:", json.dumps(a)[:150])

# 3. ledger + read-back through ActivityBus (the real consumer path)
before = ui.activity().get("llm", {})
print("llm before:", json.dumps(before)[:120])
ui.ledger({"ts": __import__("time").time(), "route": "lmstudio",
           "model": "nvidia/nemotron-3-nano-4b", "tokens_per_s": out["tokens_per_s"],
           "prompt": "hud design", "response": out["text"][:160],
           "kind": "ui_steer_smoke", "ok": True})
sys.path.insert(0, str(ROOT / "ENGINE/floating_brain"))
import activity_bus  # noqa: E402
bus = activity_bus.ActivityBus()
snap = bus.snapshot(include_live=True)
llm = snap.get("llm", {})
print("llm after :", json.dumps(llm)[:200])
pipe_ok = bool(llm.get("model") or llm.get("last_prompt") or llm.get("last_response"))
print("LEDGER->ACTIVITY PIPE:", "OK" if pipe_ok else "BROKEN")
sys.exit(0 if (out["text"] and pipe_ok) else 1)
