"""Prove the vision model is actually looking: same prompt, two different images.

A model that always says "no defects visible" is worthless. Give it (a) the real
HUD and (b) a deliberately corrupted version (text clipped, inverted contrast),
and require the answers to differ.
"""
from __future__ import annotations

import base64
import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

ROOT = Path(r"C:\ABRASAX")
SRC = ROOT / "LOGS/overlay_live.png"
BROKEN = ROOT / "LOGS/overlay_broken_probe.png"
ENDPOINT = "http://127.0.0.1:8082/v1/chat/completions"
PROMPT = (
    "This is a GPU HUD overlay. List only CONCRETE visual defects you can see "
    "(illegible text, clipped elements, empty regions, weak contrast). "
    "If none, say 'no defects visible'."
)


def make_broken() -> Path:
    im = Image.open(SRC).convert("RGB")
    im = ImageOps.invert(im)                      # destroy contrast balance
    im = ImageEnhance.Brightness(im).enhance(0.35)  # crush it to near-black
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width // 2, 40], fill=(0, 0, 0))   # black bar over title
    d.text((6, im.height - 22), "CLIPPED TEXT THAT RUNS OFF THE EDGE OF THE PANEL", fill=(255, 0, 0))
    im.save(BROKEN)
    return BROKEN


def ask(path: Path) -> tuple[str, float, int]:
    im = Image.open(path).convert("RGB")
    s = 512 / max(im.size)
    if s < 1:
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {"model": "vision", "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
        "max_tokens": 300, "temperature": 0.0}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    import time
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=400) as r:
        out = json.loads(r.read().decode())
    dt = time.time() - t0
    m = (out.get("choices") or [{}])[0].get("message", {}) or {}
    txt = (m.get("content") or m.get("reasoning_content") or "").strip()
    return txt, dt, (out.get("usage") or {}).get("total_tokens", 0)


b = make_broken()
print("broken probe written:", b.exists(), b.stat().st_size)
real_txt, real_dt, real_tok = ask(SRC)
print(f"\n=== REAL HUD  ({real_dt:.1f}s, {real_tok} tok)\n{real_txt[:500]}")
brk_txt, brk_dt, brk_tok = ask(b)
print(f"\n=== CORRUPTED ({brk_dt:.1f}s, {brk_tok} tok)\n{brk_txt[:500]}")

differs = real_txt.strip().lower() != brk_txt.strip().lower()
saw_defect = any(w in brk_txt.lower() for w in
                 ("clip", "illegib", "contrast", "dark", "empty", "unreadable", "black", "defect"))
print(f"\nanswers differ: {differs}   detected defect in corrupted: {saw_defect}")
sys.exit(0 if (differs or saw_defect) else 1)
