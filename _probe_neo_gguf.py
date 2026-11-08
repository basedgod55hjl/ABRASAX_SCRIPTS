"""_probe_neo_gguf.py - read MODELS/gguf/ABRASAX-NEO.gguf metadata (read-only).

Why: llama.cpp refused it with "unknown model architecture: 'neo'". That claim
should be checkable without llama.cpp, so this parses the GGUF header and prints
the first metadata key/values (architecture in particular).
"""
from __future__ import annotations

import struct
from pathlib import Path

PATH = Path(r"C:\abrasax\MODELS\gguf\ABRASAX-NEO.gguf")

# GGUF metadata value types -> (struct fmt, size)
SCALARS = {0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2),
           4: ("<I", 4), 5: ("<i", 4), 6: ("<f", 4), 7: ("<?", 1),
           10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8)}


def _read_string(fh) -> str:
    (n,) = struct.unpack("<Q", fh.read(8))
    return fh.read(n).decode("utf-8", "replace")


def _read_value(fh, vtype: int):
    if vtype == 8:                      # string
        return _read_string(fh)
    if vtype == 9:                      # array
        atype, n = struct.unpack("<IQ", fh.read(12))
        return [_read_value(fh, atype) for _ in range(min(n, 8))]
    fmt, size = SCALARS[vtype]
    return struct.unpack(fmt, fh.read(size))[0]


def main() -> int:
    with PATH.open("rb") as fh:
        magic = fh.read(4)
        if magic != b"GGUF":
            print("not a GGUF:", magic)
            return 1
        version, n_tensors, n_kv = struct.unpack("<IQQ", fh.read(20))
        print(f"file        {PATH}")
        print(f"size        {PATH.stat().st_size} bytes")
        print(f"gguf        v{version}  tensors={n_tensors}  kv={n_kv}")
        for _ in range(n_kv):
            key = _read_string(fh)
            (vtype,) = struct.unpack("<I", fh.read(4))
            val = _read_value(fh, vtype)
            shown = val if not isinstance(val, list) else f"[{len(val)} items]"
            print(f"  {key:34s} {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
