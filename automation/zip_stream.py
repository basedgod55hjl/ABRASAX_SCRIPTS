"""Stream a large directory into a zip without holding it in memory.

Why not Compress-Archive: on 18,858 small files it burned 159 s of CPU while the
output file stopped growing at 266 KB -- it materialises entries in memory and
thrashes. ZipFile.CreateFromDirectory streams and is bounded.

Writes a ZIP, then reopens it and compares the entry count against the source
count. The archive is only trustworthy once that round-trip matches.
"""
from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

SRC = Path(sys.argv[1])
DST = Path(sys.argv[2])

n_src = sum(1 for _ in SRC.rglob("*") if _.is_file())
print(f"source : {SRC}  ({n_src} files)")
t0 = time.time()
with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for i, p in enumerate(SRC.rglob("*"), 1):
        if p.is_file():
            zf.write(p, p.relative_to(SRC).as_posix())
        if i % 2000 == 0:
            print(f"  {i} entries  {DST.stat().st_size/1e6:.1f} MB  {time.time()-t0:.0f}s", flush=True)
print(f"written: {DST.stat().st_size/1e6:.1f} MB in {time.time()-t0:.0f}s")

with zipfile.ZipFile(DST) as zf:
    bad = zf.testzip()
    n_dst = len(zf.infolist())
print(f"verify : entries={n_dst}  src={n_src}  match={n_dst == n_src}  corrupt_entry={bad}")
sys.exit(0 if (n_dst == n_src and bad is None) else 1)
