"""vlc_vision_test.py — ABRASAX "AI SEES VIDEO" live test.
Grabs the current screen (VLC frame), sends it to a local LM Studio vision model,
and prints what the AI sees. Prove: live frame -> VRAM -> vision model -> words.

Usage: python vlc_vision_test.py ["custom prompt"]
"""
import base64
import io
import json
import os
import sys
import urllib.request

from PIL import ImageGrab
try:  # ABRASAX_JEV
    from abrasax_jev import decide as jev_decide, yesno as jev_yesno  # noqa: F401
except Exception:
    jev_decide = jev_yesno = None

MODEL = os.environ.get("VISION_MODEL", "gemma-4-e4b-it-obliterated-i1")
API = "http://127.0.0.1:1234/v1/chat/completions"
KEY = (
    os.environ.get("LM_STUDIO_API_KEY")
    or os.environ.get("ABRASAX_LMSTUDIO_KEY", "")
)


def grab_b64(max_w=1024):
    img = ImageGrab.grab()  # full virtual desktop (all monitors)
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "This is a live frame of a Windows desktop. A video is playing in a media player. "
        "Describe briefly what you can see on screen (1-2 sentences)."
    )
    b64 = grab_b64()
    body = {
        "model": MODEL,
        "max_tokens": int(os.environ.get("MAX_TOKENS", "200")),
        "temperature": 0.3,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("TIMEOUT", "180"))) as r:
            resp = json.load(r)
        print(resp["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        print(f"[HTTP {e.code}] {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
