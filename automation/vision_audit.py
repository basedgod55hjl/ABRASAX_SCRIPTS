"""Send the live overlay frame to the locally-built vision server (:8082).

This is the step LM Studio could never complete. Downscales the frame, sends it
as a data URL, and prints the model's audit verbatim.
"""
from __future__ import annotations

import base64
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

SRC = Path(r"C:\ABRASAX\LOGS\overlay_live.png")
ENDPOINT = "http://127.0.0.1:8082/v1/chat/completions"
MAX_PX = 512

im = Image.open(SRC).convert("RGB")
if max(im.size) > MAX_PX:
    s = MAX_PX / max(im.size)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
buf = io.BytesIO()
im.save(buf, format="PNG", optimize=True)
b64 = base64.b64encode(buf.getvalue()).decode("ascii")
print(f"frame {SRC.name} -> {im.size} {len(buf.getvalue())}B png, {len(b64)} b64 chars")

prompt = (
    "This is a live GPU HUD overlay rendered with OpenGL/ImGui. "
    "List only CONCRETE visual defects you can actually see: illegible or "
    "overlapping text, panels clipped at the edges, empty regions, weak contrast. "
    "Be specific and brief. If it looks correct, say 'no defects visible'."
)
payload = {
    "model": "vision",
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]}],
    "max_tokens": 900,
    "temperature": 0.1,
}

req = urllib.request.Request(
    ENDPOINT, data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=420) as r:
        out = json.loads(r.read().decode())
except Exception as exc:  # noqa: BLE001
    print("REQUEST FAILED:", type(exc).__name__, str(exc)[:300])
    sys.exit(1)
dt = time.time() - t0
msg = (out.get("choices") or [{}])[0].get("message", {}) or {}
text = (msg.get("content") or "").strip()
usage = out.get("usage") or {}
print(f"http ok  {dt:.1f}s  tokens={usage.get('total_tokens')}")
print("=== VISION AUDIT ===")
print(text or "(empty content)")
Path(r"C:\ABRASAX\DATA\r-vision2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
sys.exit(0 if text else 2)
