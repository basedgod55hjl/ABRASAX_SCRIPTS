"""Structural checks on the generated boblight.conf.

Deletes nothing and needs no hardware: it verifies the properties that make a
boblight config actually work -- channel numbering is a continuous 1..3N with no
gaps or duplicates, every light has exactly 3 colour lines, and every hscan /
vscan sits within 0..100.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CONF = Path(r"C:\ABRASAX\DATA\runtime-memory\boblight.conf")
text = CONF.read_text(encoding="utf-8")

blocks = re.split(r"^\[light\]\s*$", text, flags=re.M)[1:]
print(f"light blocks: {len(blocks)}")

chan: list[int] = []
bad_bounds: list[str] = []
bad_colors: list[str] = []
names: list[str] = []

for b in blocks:
    name = re.search(r"^name\s+(\S+)", b, re.M)
    names.append(name.group(1) if name else "?")
    cols = re.findall(r"^color\s+(\w+)\s+\S+\s+(\d+)", b, re.M)
    if len(cols) != 3 or [c[0] for c in cols] != ["red", "green", "blue"]:
        bad_colors.append(names[-1])
    chan += [int(c[1]) for c in cols]
    for key in ("hscan", "vscan"):
        m = re.search(rf"^{key}\s+([\d.]+)", b, re.M)
        if not m or not (0.0 <= float(m.group(1)) <= 100.0):
            bad_bounds.append(f"{names[-1]}.{key}")

expected = list(range(1, 3 * len(blocks) + 1))
print(f"channels used: {min(chan)}..{max(chan)}, count={len(chan)}")
print("channels continuous 1..3N, no gaps/dupes:", chan == expected)
print("every light has red/green/blue in order:", not bad_colors, bad_colors or "")
print("all hscan/vscan within 0..100:", not bad_bounds, bad_bounds or "")
print("light names unique:", len(names) == len(set(names)))

ok = chan == expected and not bad_colors and not bad_bounds and len(names) == len(set(names))
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
