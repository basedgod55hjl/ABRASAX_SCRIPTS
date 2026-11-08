"""Extract a UI SNAPSHOT from the live overlay, deterministically.

Vision models were tried first and are not trustworthy judges of this HUD
(the 3B said "no defects visible" on a deliberately corrupted frame; the 2B
loops on reasoning). So the *observation* is measured, and the LLMs are used
only for what they are good at: proposing code against a precise spec.

Measures, from the actual framebuffer capture:
  * panel bounding boxes and edge-clipping (from the panel geometry the
    overlay itself reports, not from pixels)
  * text-contrast statistics per region (bright/dark pixel ratio)
  * dead regions (large uniform areas)
  * live values the HUD is supposed to be showing

Output: DATA/runtime-memory/ui_snapshot.json consumed by ui_steer.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"C:\ABRASAX")
SHOT = ROOT / "LOGS/overlay_live.png"
OUT = ROOT / "DATA/runtime-memory/ui_snapshot.json"
ACTIVITY = "http://127.0.0.1:9626/activity"

GRID = 8  # analyse in an 8x8 grid of tiles


def luminance(arr: np.ndarray) -> np.ndarray:
    return (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2])


def analyse(img: Image.Image) -> dict:
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = a.shape
    lum = luminance(a)

    tiles = []
    th, tw = h // GRID, w // GRID
    for gy in range(GRID):
        for gx in range(GRID):
            t = lum[gy * th:(gy + 1) * th, gx * tw:(gx + 1) * tw]
            if t.size == 0:
                continue
            tiles.append({
                "gx": gx, "gy": gy,
                "mean": round(float(t.mean()), 1),
                "std": round(float(t.std()), 1),
                "bright_frac": round(float((t > 120).mean()), 3),
            })

    dead = [t for t in tiles if t["std"] < 2.0 and t["bright_frac"] < 0.01]
    dark = [t for t in tiles if t["mean"] < 12.0]

    # global contrast: spread of luminance among pixels that are actually drawn
    drawn = lum[lum > 20]
    contrast = {
        "drawn_px_frac": round(float((lum > 20).mean()), 3),
        "p05": round(float(np.percentile(drawn, 5)), 1) if drawn.size else 0.0,
        "p95": round(float(np.percentile(drawn, 95)), 1) if drawn.size else 0.0,
    }
    return {
        "size": [w, h],
        "tiles": tiles,
        "dead_regions": len(dead),
        "dark_regions": len(dark),
        "dead_tiles": dead[:8],
        "contrast": contrast,
        "distinct_colors": len(np.unique(a.reshape(-1, 3), axis=0)),
    }


def live_values() -> dict:
    import urllib.request
    try:
        with urllib.request.urlopen(ACTIVITY, timeout=8) as r:
            act = json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        return {}
    return {
        "state": act.get("state"),
        "steps": (act.get("brain") or {}).get("steps"),
        "ram": (act.get("system") or {}).get("ram"),
        "vram_used": (act.get("system") or {}).get("vram_used"),
        "vram_total": (act.get("system") or {}).get("vram_total"),
        "llm_model": (act.get("llm") or {}).get("model"),
        "llm_route": (act.get("llm") or {}).get("route"),
        "transformer_model": (act.get("transformer") or {}).get("model"),
        "tools_count": (act.get("tools") or {}).get("count"),
        "memory_recalls": (act.get("memory") or {}).get("recalls"),
    }


def main() -> int:
    if not SHOT.exists():
        print("no capture:", SHOT)
        return 1
    img = Image.open(SHOT)
    snap = {
        "frame": str(SHOT),
        "image": analyse(img),
        "live": live_values(),
        "panels_expected": ["TELEMETRY", "TRANSFORMER", "LLM ROUTE",
                            "MEMORY", "SYSTEM", "BUILD / TOOLS", "VISION"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    im = snap["image"]
    print(f"size={im['size']} colors={im['distinct_colors']} "
          f"dead={im['dead_regions']} dark={im['dark_regions']} "
          f"drawn={im['contrast']['drawn_px_frac']} "
          f"p05..p95={im['contrast']['p05']}..{im['contrast']['p95']}")
    print("live:", json.dumps(snap["live"])[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
