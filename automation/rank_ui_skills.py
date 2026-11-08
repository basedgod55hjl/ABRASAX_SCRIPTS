#!/usr/bin/env python
"""Rank UI skills by evidence, not by prose.

Signal = (a) domain weight, (b) whether the skill ships runnable assets, and
critically (c) whether it targets a technology the ABRASAX UI actually uses.
A skill that just *mentions* "panel" in passing must not outrank the one that
ships a working renderer.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
BRAIN = ROOT / "DATA/runtime-memory/ui_brain.json"

# Technologies the live UI is actually built on (see ABRAX_LAYER_CONTRACT.md).
STACK = {
    "imgui": 20,          # overlay is imgui + glfw + OpenGL
    "opengl": 18,
    "glfw": 16,
    "glsl": 16,
    "dearpygui": 14,
    "p5js": 10,           # same GL/shader muscle
    "flutter": 4,
    "maui": 4,
    "winui": 12,
    "win32": 14,
    "dwm": 12,
    "d3d": 14,
    "dxgi": 12,
    "shadcn": 4,
    "react": 3,
    "tailwind": 3,
    "html": 2,
}
STACK_RX = {k: re.compile(rf"\b{re.escape(k)}\b|{k}", re.I) for k in STACK}

PENALTY_RX = re.compile(r"(duplicate|stub|placeholder|deprecated|wip|todo)", re.I)


def stack_hits(text: str) -> tuple[int, list[str]]:
    total, hit = 0, []
    for tok, weight in STACK.items():
        if STACK_RX[tok].search(text):
            total += weight
            hit.append(tok)
    return total, hit


def main() -> int:
    b = json.loads(BRAIN.read_text(encoding="utf-8"))
    for r in b["skills"]:
        p = Path(r["path"])
        text = p.read_text(encoding="utf-8", errors="replace")[:6000]
        s_score, s_hits = stack_hits(f"{r['name']} {r['description']} {text}")
        r["stack"] = s_hits
        r["stack_score"] = s_score
        r["evidence"] = "assets" if r["assets"] > 3 else "prose"
        r["total"] = r["score"] + s_score + min(6, r["assets"])
        if PENALTY_RX.search(r["description"]):
            r["total"] -= 5
    b["skills"].sort(key=lambda r: (-r["total"], r["name"].lower()))
    BRAIN.write_text(json.dumps(b, indent=1), encoding="utf-8")
    print(f"rescored {len(b['skills'])} entries")
    for r in b["skills"][:18]:
        print(f"{r['total']:>4}  {r['name'][:34]:34} stack={','.join(r['stack'])[:34]:34} assets={r['assets']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
