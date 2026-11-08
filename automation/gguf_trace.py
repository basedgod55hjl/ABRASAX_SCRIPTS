"""Trace the GGUF header parse byte by byte to find the desync.

The v3 layout is: magic, u32 version, u64 tensor_count, u64 kv_count, then
kv pairs of (gstr key, u32 type, value). Anything else is a bug in the reader.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

p = Path(sys.argv[1])
fh = p.open("rb")

magic = struct.unpack("<I", fh.read(4))[0]
version = struct.unpack("<I", fh.read(4))[0]
n_tensors = struct.unpack("<Q", fh.read(8))[0]
n_kv = struct.unpack("<Q", fh.read(8))[0]
print(f"magic={magic:#x} version={version} tensors={n_tensors} kv={n_kv}")
print(f"file size={p.stat().st_size}")


def gstr(v: int) -> str:
    n = struct.unpack("<I", fh.read(4))[0] if v < 3 else struct.unpack("<Q", fh.read(8))[0]
    if n > 1_000_000:
        raise SystemExit(f"ABSURD string length {n} at offset {fh.tell()-8}")
    return fh.read(n).decode("utf-8", "replace")


SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?",
          9: "<Q", 10: "<q", 11: "<d"}

for i in range(min(n_kv, 12)):
    off = fh.tell()
    key = gstr(version)
    vt = struct.unpack("<I", fh.read(4))[0]
    if vt == 8:
        val = gstr(version)
    elif vt == 9:
        at = struct.unpack("<I", fh.read(4))[0]
        n = struct.unpack("<Q", fh.read(8))[0]
        if at == 8:
            val = f"[{n} strings] first={gstr(version)[:40] if n else ''}"
            for _ in range(n - 1):
                gstr(version)
        else:
            sz = struct.calcsize(SCALAR[at])
            fh.read(sz * n)
            val = f"[{n} x type{at}]"
    elif vt in SCALAR:
        val = struct.unpack(SCALAR[vt], fh.read(struct.calcsize(SCALAR[vt])))[0]
    else:
        raise SystemExit(f"UNKNOWN type {vt} for key {key!r} at offset {off}")
    print(f"  [{i:2}] @{off:<8} {key:<40} type={vt:<2} = {str(val)[:70]}")
print("parsed OK")
