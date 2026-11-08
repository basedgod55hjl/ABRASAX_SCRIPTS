"""Vision/text extraction for ABRASAX ingest using DeepSeek V4.1 Flash (NVIDIA NIM).

Reads images (seed artifacts, screenshots), asks for literal transcription of all
text plus a short structural description, saves per-image transcripts.

Usage:
  python vision_extract.py <img...>            # explicit files
  python vision_extract.py --dir <dir>         # all images in dir
  python vision_extract.py --dir <dir> --out <dir> --limit N
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path("C:/ABRASAX")
ENV = ROOT / ".env"
MODEL = os.environ.get("VISION_MODEL", "meta/llama-3.2-11b-vision-instruct")
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


def load_keys() -> list[str]:
    keys = []
    try:
        for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("NVIDIA_API_KEY_") and "=" in line:
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
                if k:
                    keys.append(k)
    except Exception:
        pass
    for name in ("NVIDIA_API_KEY_1", "NVIDIA_API_KEY_2", "NVIDIA_API_KEY"):
        v = os.environ.get(name)
        if v and v not in keys:
            keys.append(v)
    return keys


PROMPT = (
    "You are an OCR + vision extraction engine. Transcribe ALL text in this image "
    "verbatim (preserve line structure; note if text is stylized/unreadable). "
    "Then describe the image in 3-6 sentences: what it shows, any code, QR codes, "
    "diagrams, sigils, schematics, UI elements, numbers, or embedded payload-looking "
    "data. If it is a QR code, state that and transcribe any visible label. "
    "Output plain text only, sections: TRANSCRIPT: / DESCRIPTION:"
)


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def extract(path: Path, keys: list[str], key_idx: list[int]) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri(path)}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2600,
    }
    last_err = None
    for attempt in range(len(keys)):
        key = keys[(key_idx[0] + attempt) % len(keys)]
        try:
            r = requests.post(URL, json=payload, timeout=300, headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                key_idx[0] = (key_idx[0] + attempt + 1) % len(keys)
                j = r.json()
                msg = (j.get("choices") or [{}])[0].get("message", {})
                return {
                    "ok": True,
                    "path": str(path),
                    "model": MODEL,
                    "content": (msg.get("content") or "").strip(),
                    "reasoning": (msg.get("reasoning_content") or "")[:4000],
                    "usage": j.get("usage"),
                }
            last_err = f"http {r.status_code}: {r.text[:200]}"
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2)
                continue
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(2)
    return {"ok": False, "path": str(path), "error": last_err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--out", default=str(ROOT / "DATA" / "telegram-desktop" / "vision"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    targets: list[Path] = [Path(p) for p in args.images]
    if args.dir:
        targets += sorted(p for p in Path(args.dir).rglob("*") if p.suffix.lower() in EXTS)
    targets = [p for p in targets if p.is_file()]
    if args.limit:
        targets = targets[: args.limit]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = load_keys()
    if not keys:
        sys.exit("no NVIDIA keys found")
    key_idx = [0]
    results_path = out_dir / "vision-results.jsonl"
    ok = err = 0
    import threading
    lock = threading.Lock()

    def work(path: Path) -> str:
        nonlocal ok, err
        res = extract(path, keys, key_idx)
        res["ts"] = datetime.now(timezone.utc).isoformat()
        with lock:
            with results_path.open("a", encoding="utf-8") as rf:
                rf.write(json.dumps(res, ensure_ascii=False) + "\n")
            if res["ok"]:
                ok += 1
                txt = out_dir / (path.stem.replace(" ", "_")[:120] + ".vision.txt")
                txt.write_text(res["content"], encoding="utf-8")
            else:
                err += 1
            done = ok + err
        print(f"[{done}/{len(targets)}] {'OK' if res['ok'] else 'ERR'} {path.name}"
              + ("" if res["ok"] else f" :: {res.get('error', '')[:120]}"), flush=True)
        return path.name

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(work, targets))
    print(f"DONE ok={ok} err={err} -> {results_path}")


if __name__ == "__main__":
    main()
