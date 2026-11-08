"""Decode the VectorRamp stubs -- same guard pattern, or something else?

Given bytes:
  VectorRamp_32f @0x16411C0: 0f 28 e9 0f 28 e0 48 85 ff 0f ...
  VectorRamp_64f @0x1671680: 48 85 ff 0f 84 49 01 00 00 85 ...

The 32f/64f prologues start with DIFFERENT bytes (0f 28 vs 48 85), unlike the
Interleave pair which shared 11 bytes. So there is no shared guard here; check
what each does independently.

Also: the earlier "selector" read at 0x1FBDF68 / 0x1FBB4C8 returned
ffffffff 00000000..., which is -1 + zeros, NOT a pointer table. That claim is
retracted; this script does not revive it.
"""
from __future__ import annotations

from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

P = Path(r"C:\abrasax\_DEAD_PATH\fl_unpack\Library\Audio\Plug-Ins\VST"
         r"\FL Studio VSTi.vst\Contents\Resources\Shared\dsp_ippv2_x64.dylib")

SLICE_OFF = 0x4000
TARGETS = {
    "VectorRamp_32f": 0x16411C0,
    "VectorRamp_64f": 0x1671680,
}
WINDOW = 48

body = P.read_bytes()[SLICE_OFF:]

# minimal x86-64 decoder for the opcodes that actually appear here.
OPC = {
    (0x0F, 0x28): ("movaps", "load packed singles from xmm"),
    (0x0F, 0x29): ("movaps", "store packed singles to xmm"),
    (0x0F, 0x84): ("je", "jump if ZF"),
    (0x0F, 0x85): ("jne", "jump if !ZF"),
    (0x0F, 0x8E): ("jle", "jump if ZF or SF!=OF"),
    (0x0F, 0x8F): ("jg", "jump if !ZF and SF==OF"),
}

for name, addr in TARGETS.items():
    chunk = body[addr:addr + WINDOW]
    print(f"\n--- {name} @0x{addr:X}")
    print(f"    {chunk.hex(' ')}")
    i = 0
    while i < len(chunk) - 1:
        b = chunk[i]
        nxt = chunk[i + 1]
        if b == 0x0F and nxt in (0x28, 0x29) and i + 2 < len(chunk):
            modrm = chunk[i + 2]
            mnem, note = OPC[(0x0F, nxt)]
            reg = (modrm >> 3) & 7
            rm = modrm & 7
            print(f"    +{i:02d}  0f {nxt:02x} {modrm:02x}   {mnem:8} "
                  f"xmm{reg}, xmm{rm}   ({note})")
            i += 3
            continue
        if b == 0x0F and nxt in (0x84, 0x85, 0x8E, 0x8F) and i + 6 <= len(chunk):
            disp = int.from_bytes(chunk[i + 2:i + 6], "little", signed=True)
            mnem, note = OPC[(0x0F, nxt)]
            print(f"    +{i:02d}  0f {nxt:02x} {chunk[i+2:i+6].hex()}   {mnem:8} "
                  f"target = here+{disp:#x}  ({note})")
            i += 6
            continue
        if b == 0x48 and i + 3 <= len(chunk):
            n2 = chunk[i + 1]
            if n2 == 0x85:
                modrm = chunk[i + 2]
                reg = (modrm >> 3) & 7
                rm = modrm & 7
                print(f"    +{i:02d}  48 85 {modrm:02x}      test   "
                      f"r{reg if reg > 7 else reg}, r{rm}")
                i += 3
                continue
        # fallback: single byte, keep going
        i += 1
