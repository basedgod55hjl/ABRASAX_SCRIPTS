#!/usr/bin/env python
"""Extract descriptions (and UI-relevance) from every SKILL.md under AGENTS/SKILLS.

Ground truth: parses the YAML front matter we actually have on disk. Emits JSON
to LOGS/skill-inventory.json and prints per-skill one-liners.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOTS = [
    Path(r"C:\ABRASAX\AGENTS\SKILLS\source-skills"),
    Path(r"C:\ABRASAX\AGENTS\SKILLS\rust-skills"),
]
PRUNE = {"node_modules", ".git", ".gradle", "__pycache__", "target", "dist"}
UI_RX = re.compile(
    r"imgu|dear.?pygui|pyopengl|opengl|\bglfw\b|glsl|shader|holograph|panel|"
    r"\bui\b|\bux\b|design|layout|visual|render|overlay|dashboard|dpi|dwm|"
    r"win32|winui|direct3d|d3d|dxgi|window composition|acrylic|mica|theme|color|typograph",
    re.I,
)


def front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end]
    out: dict = {}
    key = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][\w-]*:", raw):
            key, _, val = raw.partition(":")
            key = key.strip()
            out[key] = val.strip().strip('"').strip("'")
        elif key and raw.startswith((" ", "\t")):
            # folded continuation of a block scalar / long value
            out[key] = (out.get(key, "") + " " + raw.strip()).strip()
    return out


def body_head(text: str, limit: int = 600) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            text = text[end + 4:]
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[#*>`|_-]{2,}", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:limit]


def scan() -> list[dict]:
    rows = []
    for root in ROOTS:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in PRUNE]
            if "SKILL.md" not in filenames:
                continue
            p = Path(dirpath) / "SKILL.md"
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = front_matter(text)
            name = fm.get("name") or p.parent.name
            desc = fm.get("description") or ""
            head = body_head(text)
            blob = f"{name} {desc} {head}"
            rows.append(
                {
                    "name": name,
                    "dir": p.parent.name,
                    "rel": str(p.relative_to(root)),
                    "root": root.name,
                    "bytes": p.stat().st_size,
                    "description": desc[:400],
                    "ui_score": len(UI_RX.findall(blob)),
                    "first_heading": next(
                        (
                            ln.lstrip("# ").strip()
                            for ln in text.splitlines()
                            if ln.startswith("#")
                        ),
                        "",
                    ),
                }
            )
    rows.sort(key=lambda r: (-r["ui_score"], r["name"].lower()))
    return rows


def main() -> int:
    rows = scan()
    out = Path(r"C:\ABRASAX\LOGS\skill-inventory.json")
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"skills={len(rows)} -> {out}")
    for r in rows[:40]:
        print(f"{r['ui_score']:>4}  {r['name'][:38]:38}  {r['description'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
