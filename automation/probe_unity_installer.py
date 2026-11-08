"""Probe whether the 3.7 GB Unity installer is worth compressing.

UnitySetup64 is a self-extracting archive whose payload is already compressed
(7z/lzma). Re-compressing it should yield ~0%, in which case archiving it is
pure waste: the right outcome is "keep it, or delete it because it is
re-downloadable", NOT "make a second 3.7 GB copy".
"""
from __future__ import annotations

import zlib
from pathlib import Path

SRC = Path(r"C:\ABRASAX\BUILD\installers\UnitySetup64-6000.6.6f1.exe")

with SRC.open("rb") as fh:
    head = fh.read(4)
    fh.seek(0)
    chunk = fh.read(4 * 1024 * 1024)

print(f"file: {SRC.name}  {SRC.stat().st_size/1e9:.2f} GB")
print("magic:", head.hex(" "), "|", head[:2])
comp = zlib.compress(chunk, 6)
print(f"first {len(chunk)/1e6:.0f} MB -> {len(comp)/1e6:.2f} MB compressed "
      f"({100*len(comp)/len(chunk):.1f}%)")
ratio = len(comp) / len(chunk)
if ratio > 0.9:
    print("VERDICT: already compressed / incompressible -> archiving would waste space.")
    print("         Recommended: keep it, or delete it (re-downloadable), not archive.")
else:
    print(f"VERDICT: compressible (~{100*(1-ratio):.0f}% saving) -> archiving is worthwhile.")
