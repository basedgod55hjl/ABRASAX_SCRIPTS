"""Do legacy90 kernels share code with modern ones, or are they separate bodies?

The structural partition proves different SLOTS. It does not prove different
CODE -- the linker could fold identical functions (ICF). This resolves one stub
per selector and compares:

  * the slot address each stub loads from   (pointer topology, already measured)
  * the value stored in that slot            (the resolved kernel address)
  * the first bytes of code at that target   (whether bodies are distinct)

If legacy and modern both resolve to the same target, the kernels are aliased
and the "separate implementations" reading is wrong. If targets differ, the
modules really are independent at the code level too.

Naming: modern ipps* exports carry no legacy90 prefix; legacy ones do.
"""
from __future__ import annotations

import struct
from collections import defaultdict
from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

P = Path("C:/abrasax/_DEAD_PATH/fl_unpack/Library/Audio/Plug-Ins/VST/"
         "FL Studio VSTi.vst/Contents/Resources/Shared/dsp_ippv2_x64.dylib")

FAT_MAGIC, MH_MAGIC_64 = 0xCAFEBABE, 0xFEEDFACF
LC_SYMTAB = 0x2
NLIST_64 = struct.Struct("<IBBHQ")
N_EXT, N_SECT = 0x01, 0x0E

data = P.read_bytes()


def fat(buf):
    if struct.unpack(">I", buf[:4])[0] != FAT_MAGIC:
        return []
    n = struct.unpack(">I", buf[4:8])[0]
    return [struct.unpack(">iiIII", buf[8 + i * 20:28 + i * 20]) for i in range(n)]


def read_syms(buf, off):
    """-> {name: vmaddr} for external defined symbols."""
    if struct.unpack("<I", buf[off:off + 4])[0] != MH_MAGIC_64:
        return {}
    ncmds = struct.unpack("<I", buf[off + 16:off + 20])[0]
    pos, st = off + 32, None
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack("<II", buf[pos:pos + 8])
        if cmd == LC_SYMTAB:
            st = struct.unpack("<IIII", buf[pos + 8:pos + 24])
            break
        pos += cmdsize
    if not st:
        return {}
    symoff, nsyms, stroff, strsize = st
    strtab = buf[off + stroff:off + stroff + strsize]
    out = {}
    for i in range(nsyms):
        b = off + symoff + i * NLIST_64.size
        strx, ntype, nsect, _d, val = NLIST_64.unpack(buf[b:b + NLIST_64.size])
        if not (ntype & N_EXT) or (ntype & N_SECT) != N_SECT:
            continue
        if strx >= strsize:
            continue
        end = strtab.find(b"\0", strx)
        name = strtab[strx:end if end > 0 else None].decode("latin-1")
        if name:
            out[name] = val
    return out


for ct, _sub, off, size, _al in fat(data):
    if ct != 0x01000007:
        continue
    syms = read_syms(data, off)
    print(f"x86_64: {len(syms)} external defined symbols\n")

    # each export is a 3-opcode stub: 48 8d 05 <disp32> (lea) then more
    rows = []
    for name, addr in syms.items():
        if "legacy90" not in name:
            continue
        code = data[off + addr:off + addr + 8]
        if code[:3] != b"\x48\x8d\x05":
            continue
        disp = struct.unpack("<i", code[3:7])[0]
        slot_va = addr + 7 + disp          # lea rax,[rip+disp] -> slot in __DATA
        rows.append((name, addr, slot_va))

    print(f"legacy90 stubs with lea form: {len(rows)}")
    # group by resolved slot
    by_slot = defaultdict(list)
    for name, addr, slot in rows:
        by_slot[slot].append(name)

    print("\nslot -> legacy exports using it")
    for slot, names in sorted(by_slot.items(), key=lambda kv: -len(kv[1])):
        print(f"  slot 0x{slot:X}  ({len(names)} exports)")
        for n in sorted(names)[:4]:
            print(f"      {n}")
        if len(names) > 4:
            print(f"      ... +{len(names) - 4} more")

    # what does one slot hold?
    print("\nslot CONTENTS (the resolved kernel pointer, if any):")
    for slot in sorted(by_slot):
        val = struct.unpack("<Q", data[off + slot:off + slot + 8])[0]
        inside = 0 < val < size
        note = ""
        if inside:
            tgt = data[off + val:off + val + 12]
            note = f"  target bytes: {tgt.hex(' ')}"
        print(f"  0x{slot:X} -> 0x{val:X}  "
              f"{'points into slice' if inside else 'zero / outside slice'}{note}")
