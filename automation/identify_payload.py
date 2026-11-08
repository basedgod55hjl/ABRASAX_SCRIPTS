"""Identify the 2.34 GB Payload~ container.

Earlier a bare 8-byte read gave `07 07 07 00`, which matches no standard archive
magic. Options: a raw filesystem image, a vendor packer, a sparse/encrypted blob,
or a format whose header sits at a non-zero offset.

This scans for known magics anywhere in the first several MB, reports byte
entropy (encrypted/compressed data is ~8.0 bits/byte; a filesystem image or an
uncompressed bundle is far lower), and looks for the FL Studio bundle's own
strings so we can tell whether the payload is even inside this file.
"""
from __future__ import annotations

import math
import struct
import sys
from collections import Counter
from pathlib import Path

P = Path(r"J:\Sandisk_Backup\FL_Studio_Payload_Extracted\Payload~")

MAGICS = {
    b"PK\x03\x04": "ZIP local header",
    b"PK\x05\x06": "ZIP end-of-central-dir",
    b"7z\xbc\xaf\x27\x1c": "7-Zip",
    b"Rar!\x1a\x07": "RAR",
    b"\x1f\x8b\x08": "gzip",
    b"BZh": "bzip2",
    b"\xfd7zXZ\x00": "xz",
    b"\x28\xb5\x2f\xfd": "zstd",
    b"ustar": "tar (at 257)",
    b"\xca\xfe\xba\xbe": "Mach-O fat",
    b"\xcf\xfa\xed\xfe": "Mach-O 64",
    b"MZ": "PE/EXE",
    b"\x7fELF": "ELF",
    b"SQLite format 3": "SQLite",
    b"\x00\x00\x01\x00": "ICO",
    b"\x89PNG": "PNG",
    b"GIF8": "GIF",
    b"\xff\xd8\xff": "JPEG",
    b"RIFF": "RIFF/WAV",
    b"QFI\xfb": "qcow2",
    b"KDMV": "VMware VMDK",
    b"conectix": "VHD (dynamic)",
    b"APFS": "APFS block",
    b"HFSJ": "HFS+",
    b"NXSB": "APFS container superblock",
}


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


with P.open("rb") as fh:
    head = fh.read(4 * 1024 * 1024)
    print(f"file: {P.stat().st_size:,} B")
    print(f"first 32 bytes: {head[:32].hex(' ')}")

    print("\nmagic hits in first 4 MiB:")
    for magic, label in MAGICS.items():
        idx = head.find(magic)
        if idx >= 0:
            print(f"  {label:26} at 0x{idx:x}")

    print("\nentropy by 1 MiB block (8.0 = random/encrypted, <6 = structured):")
    for i in range(4):
        blk = head[i * 1048576:(i + 1) * 1048576]
        print(f"  MiB {i}: {entropy(blk):.3f} bits/byte")

    print("\nsignature search for the VST bundle markers:")
    for probe in (b"FL Studio VSTi", b"vstplugin", b"dsp_ippv2",
                  b"ILTools", b"libwinbridge", b"__TEXT", b"MH_MAGIC"):
        idx = head.find(probe)
        print(f"  {probe.decode(errors='replace'):18} {'at 0x%x' % idx if idx >= 0 else 'not in first 4 MiB'}")

    # is it sparse? compare first/last blocks
    fh.seek(-64, 2)
    tail = fh.read(64)
    print(f"\nlast 64 bytes: {tail.hex(' ')}")
    print(f"tail entropy: {entropy(tail):.3f}")
    _zero = head[:4096] == bytes(4096)
    print(f"all-zero head? {_zero}")
sys.exit(0)
