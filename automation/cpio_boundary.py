"""Confirm the cpio boundary inside Payload~ and characterise what follows it.

Given: cpio odc stream ends at 0x3055575 (50,681,205) with 80 members; the file
continues to 2,511,139,840. Verify both facts from bytes, and say what the
2.46 GB tail actually is instead of guessing.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

P = Path(r"J:\Sandisk_Backup\FL_Studio_Payload_Extracted\Payload~")
END = 0x3055575


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    c, n = Counter(b), len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


with P.open("rb") as fh:
    fh.seek(END - 16)
    around = fh.read(64)
    print(f"bytes around 0x{END:x} - 16:")
    for i in range(0, 64, 16):
        chunk = around[i:i + 16]
        print(f"  {END - 16 + i:#010x}  {chunk.hex(' ')}  "
              + "".join(chr(b) if 32 <= b < 127 else "." for b in chunk))

    fh.seek(END - 32)
    tail_trailer = fh.read(32)
    print(f"\ntrailer region: {tail_trailer.hex(' ')}")
    print("  contains '070707' TRAILER!:", b"070707000000000000000000000000000000000000000000000000000001" in tail_trailer)

    # what comes after the cpio stream
    fh.seek(END)
    after = fh.read(4096)
    print(f"\nfirst 4096 bytes after cpio end:")
    print(f"  entropy {entropy(after):.3f} bits/byte")
    print(f"  all zero: {after == bytes(len(after))}")
    print(f"  first 32: {after[:32].hex(' ')}")

    # sample the tail at intervals
    size = P.stat().st_size
    print(f"\ntail spans {END:,} .. {size:,}  ({size - END:,} bytes)")
    for frac in (0.1, 0.3, 0.5, 0.7, 0.9, 0.99):
        off = int(END + (size - END) * frac)
        fh.seek(off)
        blk = fh.read(1 << 16)
        nz = sum(1 for b in blk if b)
        print(f"  @{off:#012x} entropy {entropy(blk):.3f}  nonzero={nz}/{len(blk)}")
