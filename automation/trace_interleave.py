"""Trace whether Interleave_32f (0x19058E0) branches into Interleave_16s (0x1905A60).

Sub-group A's mechanism ("one guarded body, displaced second entry") rests on an
inference I have not tested: that control actually transfers from the first entry
into the second. The 0x180 gap is small enough to walk.

Method: from 0x19058E0, decode forward looking for rel32/rel8 branches and
jumps whose TARGET lands at or after 0x1905A60. Report every control transfer
found in the interval, with its computed destination.

A hand decoder desynced earlier (a jne that resolved to a wild address). To
avoid repeating that, this decoder is strict: it only recognises a small set of
opcodes it can size exactly, and it RESYNCS only on a known instruction start.
Anything unknown stops the scan and is reported rather than guessed past.
"""
from __future__ import annotations

from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

P = Path("C:/abrasax/_DEAD_PATH/fl_unpack/Library/Audio/Plug-Ins/VST/FL Studio VSTi.vst/Contents/Resources/Shared/dsp_ippv2_x64.dylib")

SLICE_FILEOFF = 0x4000      # x86_64 slice begins here in the fat file
VM_BASE = 0x0               # __TEXT vmaddr starts at 0; fileoff==vmaddr for slice
A = 0x19058E0               # Interleave_32f
B = 0x1905A60               # Interleave_16s
SPAN = B - A

body = P.read_bytes()[SLICE_FILEOFF:]


def target(addr: int) -> int:
    return addr - VM_BASE     # file index within the slice


# --- instruction sizes for the subset we can size with certainty -------------
def size_of(code: bytes, i: int) -> int | None:
    b = code[i]
    # REX prefix
    if 0x40 <= b <= 0x4F and i + 1 < len(code):
        return 1 + (size_of(code, i + 1) or 0) or None
    if b == 0x0F and i + 1 < len(code):
        n = code[i + 1]
        if n in (0x84, 0x85, 0x8E, 0x8F, 0x82, 0x83, 0x86, 0x87):
            return 6                      # jcc rel32
        if n in (0x80, 0x81, 0x8C, 0x8D, 0x8E, 0x8F):
            return 6                      # near jcc rel32 (variants)
        if n in (0x28, 0x29, 0x10, 0x11, 0x58, 0x59, 0x6E, 0x7E, 0xC2, 0xC6):
            return 3                      # movaps/movups class (modrm, reg-reg)
        if n == 0x1F:
            return 3
        if n == 0xB6 or n == 0xBE:
            return 4
        return None
    if b in (0xEB,):                      # jmp rel8
        return 2
    if b in (0x74, 0x75, 0x7C, 0x7D, 0x7E, 0x7F, 0xE3):
        return 2                      # jcc rel8
    if b == 0xE9:
        return 5                      # jmp rel32
    if b == 0x85:
        return 2                      # test r/m32,r32 (reg,reg)
    if b == 0x83:
        return 3                      # cmp/add/sub r/m32, imm8
    if b == 0x3D:
        return 5
    if b in (0x89, 0x8B, 0x8D, 0x31, 0x33, 0x01, 0x03, 0x29, 0x2B):
        return 3                      # mov/lea/xor/add/sub r,r
    if b in (0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
             0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F):
        return 1                      # push/pop reg
    if b in (0x90, 0xC3, 0xCC):
        return 1                      # nop / ret / int3
    if b == 0xB8:
        return 5                      # mov eax, imm32
    return None


code = body[A: B + 64]
print(f"scanning 0x{A:X} .. 0x{B:X}  ({SPAN} bytes)")
print(f"header bytes: {code[:SPAN].hex(' ')}\n")

i = 0
found = []
while i < SPAN:
    sz = size_of(code, i)
    if sz is None:
        print(f"  +0x{i:03X}  UNKNOWN opcode {code[i]:02x} -- stopping "
              f"(refusing to guess past it)")
        break
    addr = A + i
    b0 = code[i]
    # classify control transfers
    if b0 == 0xE9:
        disp = int.from_bytes(code[i + 1:i + 5], "little", signed=True)
        dest = addr + 5 + disp
        found.append((addr, "jmp rel32", dest))
    elif b0 == 0xEB:
        disp = int.from_bytes(code[i + 1:i + 2], "little", signed=True)
        found.append((addr, "jmp rel8", addr + 2 + disp))
    elif b0 in (0x74, 0x75, 0x7C, 0x7D, 0x7E, 0x7F):
        disp = int.from_bytes(code[i + 1:i + 2], "little", signed=True)
        found.append((addr, "jcc rel8", addr + 2 + disp))
    elif b0 == 0x0F and i + 1 < len(code) and code[i + 1] in (
            0x84, 0x85, 0x8E, 0x8F, 0x82, 0x83, 0x86, 0x87):
        disp = int.from_bytes(code[i + 2:i + 6], "little", signed=True)
        found.append((addr, "jcc rel32", addr + 6 + disp))
    i += sz

print(f"\nreached +0x{i:03X} of {SPAN}")
print("control transfers found:")
for addr, kind, dest in found:
    mark = ""
    if dest == B:
        mark = "  <== INTO Interleave_16s"
    elif abs(dest - B) < 0x200:
        mark = f"  (near B, delta {dest - B:+#x})"
    print(f"  0x{addr:X}  {kind:10} -> 0x{dest:X}{mark}")

into_b = [f for f in found if f[2] == B]
print(f"\nVERDICT: branch from 32f into 16s = "
      f"{'YES' if into_b else 'NOT FOUND'}")
print("  (if NOT FOUND, sub-group A's 'shared body' reading stays INFERRED)")
