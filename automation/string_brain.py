"""STRING BRAIN — drive the GPU brain field with real LLM inference.

The floating-brain renderer currently pulls a 64x64 activation field from the
synaptic brain service on :9626. That field moves, but it moves for its own
reasons: it is not an expression of anything the model just said.

This daemon closes that loop. It:
  1. asks the live LLM router a prompt (lmstudio -> nvidia -> xpl),
  2. turns the reply's token stream into a 64x64 drive field,
  3. pushes that field to the brain service so the renderer animates it.

The mapping is deliberate and documented, because "AI drives the visual" is only
meaningful if the coupling is legible:

  * each token becomes a point in the field, placed along a phi-spiral so the
    sequence reads as a filament rather than a blob,
  * the token's hash selects which of the 4096 cells it lights,
  * recency decays: earlier tokens fade, so the field shows the head of the
    thought rather than the whole transcript at once,
  * a low-amplitude standing wave keeps the field alive between replies so the
    surface never freezes mid-thought.

Usage:
    python scripts  (or)  python -m ...
      --prompt "..."      single shot
      --loop              keep cycling a topic list
      --interval 6        seconds between replies in --loop
      --dry-run           compute the field, print stats, do not push
"""
import argparse
import base64
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, r"C:\ABRASAX")

PHI = 1.61803398874989484820
PHI_INV = 0.61803398874989484820
W = H = 64
N = W * H

BRAIN = "http://127.0.0.1:9626"
RENDER = "http://127.0.0.1:9700"
DEFAULT_TOPICS = [
    "Describe what a thought feels like in one short sentence.",
    "What is the golden ratio's role in stability? One sentence.",
    "Explain phase locking to a child. One sentence.",
    "What makes a pattern feel alive? One sentence.",
    "Describe the colour of a coherent field. One sentence.",
]


# ---------------------------------------------------------------------------
# Field construction
# ---------------------------------------------------------------------------
def tokenize(text):
    """Split into token-ish chunks. We do not need a real tokenizer here --
    the renderer is driven by *placement*, and word boundaries are enough."""
    out = []
    for raw in text.replace("\n", " ").split(" "):
        t = raw.strip()
        if t:
            out.append(t)
    return out


def token_cell(tok, index, total):
    """Map one token to a cell index.

    Two forces, both visible in the output:
      * a phi-spiral along the sequence, so order is legible as a curve,
      * a hash term, so identity matters and repeated words do not collapse.
    """
    h = hashlib.sha256(tok.encode("utf-8")).digest()
    hv = int.from_bytes(h[:4], "big") / 0xFFFFFFFF

    # spiral position for this index in the sequence
    frac = (index + 1) / max(1, total)
    ang = frac * math.pi * 2.0 * PHI
    rad = (frac ** PHI_INV) * 0.46

    cx = 0.5 + math.cos(ang) * rad
    cy = 0.5 + math.sin(ang) * rad

    # hash jitter, small enough that the spiral survives
    cx += (hv - 0.5) * 0.10
    cy += (int.from_bytes(h[4:8], "big") / 0xFFFFFFFF - 0.5) * 0.10

    px = min(W - 1, max(0, int(cx * (W - 1))))
    py = min(H - 1, max(0, int(cy * (H - 1))))
    return py * W + px


def build_field(tokens, clock=0.0):
    """Turn a token list into a 4096-float field in [0,1]."""
    field = [0.0] * N
    if not tokens:
        return field

    total = len(tokens)

    # Deposit each token with a decaying 3x3 splat so neighbours read as a body.
    for i, tok in enumerate(tokens):
        # recency: head of the reply is brightest
        recency = (i + 1) / total
        energy = 0.35 + 0.65 * (recency ** PHI_INV)
        c = token_cell(tok, i, total)
        cy, cx = divmod(c, W)

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    w = 1.0 if (dx == 0 and dy == 0) else (
                        0.5 if abs(dx) + abs(dy) == 1 else 0.25)
                    field[y * W + x] += energy * w

    # Normalise to [0,1], then add a standing wave so the field breathes between
    # replies instead of freezing.
    peak = max(field) or 1.0
    for i in range(N):
        y, x = divmod(i, W)
        wave = 0.06 * (0.5 + 0.5 * math.sin(
            (x * PHI + y * PHI_INV) * 0.42 + clock * 2.0 * math.pi * 0.5))
        field[i] = min(1.0, field[i] / peak + wave)

    return field


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def post_json(url, payload, timeout=8):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()[:300]


def push_to_renderer(field, dry_run=False):
    """Push the LLM-derived field to the renderer's /drive route.

    Quantise to uint8 the same way the shader will read it, base64-encode, POST.
    The renderer stores it and the next /frame.png renders *this* instead of the
    brain feed, so the model's reply literally becomes the image.
    """
    if dry_run:
        return "dry-run"

    raw = bytes(int(max(0.0, min(1.0, v)) * 255) for v in field)
    payload = {
        "w": W,
        "h": H,
        "data": base64.b64encode(raw).decode("ascii"),
    }
    try:
        st, body = post_json(f"{RENDER}/drive", payload, timeout=10)
        if 200 <= st < 300:
            return "drive-ok"
        return f"drive-http-{st}"
    except Exception as e:  # noqa: BLE001
        return f"drive-failed ({type(e).__name__})"


def ask_llm(prompt, max_tokens=48):
    from abrasax import llm
    t0 = time.time()
    r = llm.ask(prompt, max_tokens=max_tokens)
    dt = time.time() - t0
    if isinstance(r, dict):
        text = r.get("content") or r.get("text") or ""
        return text, r.get("routed_via"), r.get("model"), dt
    return str(r), None, None, dt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Drive the brain field with live LLM output")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=float, default=6.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cycles", type=int, default=0, help="0 = forever (with --loop)")
    args = ap.parse_args()

    if not args.loop and not args.prompt:
        args.prompt = DEFAULT_TOPICS[0]

    cycle = 0
    while True:
        prompt = args.prompt or DEFAULT_TOPICS[cycle % len(DEFAULT_TOPICS)]
        try:
            text, route, model, dt = ask_llm(prompt)
        except Exception as e:  # noqa: BLE001
            print(f"[string-brain] LLM failed: {type(e).__name__}: {e}", flush=True)
            text, route, model, dt = "", None, None, 0.0

        toks = tokenize(text)
        field = build_field(toks, clock=cycle * 0.5)
        meanv = sum(field) / N
        peakv = max(field)

        result = push_to_renderer(field, args.dry_run)

        print(json.dumps({
            "cycle": cycle,
            "prompt": prompt[:60],
            "reply": text[:100],
            "routed_via": route,
            "model": model,
            "llm_s": round(dt, 3),
            "tokens": len(toks),
            "field_mean": round(meanv, 4),
            "field_peak": round(peakv, 4),
            "push": result,
        }), flush=True)

        cycle += 1
        if args.cycles and cycle >= args.cycles:
            break
        if not args.loop:
            break
        time.sleep(max(0.5, args.interval))

    return 0


if __name__ == "__main__":
    sys.exit(main())
