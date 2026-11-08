"""Disassemble the two Interleave stubs from raw bytes.

Hand-decoding x86-64 past a `0f` prefix is guesswork, and guessing is how this
thread accumulated its errors. The honest move: dump the exact instruction bytes
and decode them with the CPU's own decoder (via capstone if available), otherwise
print the byte stream in a form that can be checked by hand against the Intel
manual rather than asserted.

Also verifies the earlier claim that both stubs start with identical bytes, and
measures precisely how far the identical prefix extends.
"""
from __future__ import annotations

import struct
from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

P = Path(r"C:\abrasax\_DEAD_PATH\fl_unpack\Library\Audio\Plug-Ins\VST"
         r"\FL Studio VSTi.vst\Contents\Resources\Shared\dsp_ippv2_x64.dylib")

SLICE_OFF = 0x4000          # x86_64 slice start inside the fat file
A16 = 0x1905A60             # Interleave_16s
A32 = 0x19058E0             # Interleave_32f
WINDOW = 32

blob = P.read_bytes()
body = blob[SLICE_OFF:]

b16 = body[A16:A16 + WINDOW]
b32 = body[A32:A32 + WINDOW]

print(f"Interleave_16s @0x{A16:X}: {b16.hex(' ')}")
print(f"Interleave_32f @0x{A32:X}: {b32.hex(' ')}")

# how long is the shared prefix?
common = 0
for x, y in zip(b16, b32):
    if x != y:
        break
    common += 1
print(f"\nidentical prefix: {common} bytes  ({b16[:common].hex(' ')})")
if common < WINDOW:
    print(f"first divergence at +{common}: "
          f"16s={b16[common]:02x} 32f={b32[common]:02x}")

# try capstone
try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64  # type: ignore
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    for name, addr, code in (("Interleave_16s", A16, b16),
                             ("Interleave_32f", A32, b32)):
        print(f"\n--- {name} @0x{addr:X}")
        for ins in md.disasm(code, addr):
            print(f"  {ins.address:08X}  {ins.bytes.hex():<20} {ins.mnemonic:8} {ins.op_str}")
except ImportError:
    print("\ncapstone not installed -- install it to decode properly:")
    print("  pip install capstone")
    print("\nBytes are printed above; do NOT hand-guess past the 0f prefix.")

# what do the selectors point at?
for sel in (0x1FBDF68, 0x1FBB4C8):
    raw = body[sel:sel + 16]
    print(f"\nselector 0x{sel:X}: {raw.hex(' ')}")
    # interpret as two qwords / four dwords
    q = struct.unpack("<QQ", raw)
    d = struct.unpack("<iiii", raw)
    print(f"   as 2 x u64: {q[0]:#x} {q[1]:#x}")
    print(f"   as 4 x i32: {d}")
