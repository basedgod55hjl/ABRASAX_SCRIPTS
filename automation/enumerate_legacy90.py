"""Full enumeration of legacy90 exports -- the measurement that retires the caveats.

Standing caveats this addresses:
  1. "most legacy90 pairs are identical at entry" rests on ONE pair examined.
  2. Absence claims (no _64f interleave, no _16s ramp) came from a filtered
     print, not from enumerating the export set.

Method: read LC_SYMTAB, take every external defined symbol whose name starts
with _legacy90, group by base name (strip the precision suffix), and compare the
first 24 bytes of each member's code. Then report:
  * the complete list (so absences are visible, not assumed)
  * for each base name, whether its precision variants share an entry prefix
"""
from __future__ import annotations

import re
import struct
from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

P = Path("C:/abrasax/_DEAD_PATH/fl_unpack/Library/Audio/Plug-Ins/VST/"
         "FL Studio VSTi.vst/Contents/Resources/Shared/dsp_ippv2_x64.dylib")

FAT_MAGIC = 0xCAFEBABE
MH_MAGIC_64 = 0xFEEDFACF
LC_SYMTAB = 0x2
N_EXT, N_SECT = 0x01, 0x0E
NLIST_64 = struct.Struct("<IBBHQ")
PREFIX_BYTES = 24

data = P.read_bytes()


def fat_slices(buf):
    if struct.unpack(">I", buf[:4])[0] != FAT_MAGIC:
        return []
    n = struct.unpack(">I", buf[4:8])[0]
    out = []
    for i in range(n):
        ct, _s, off, size, _a = struct.unpack(">iiIII", buf[8 + i * 20:28 + i * 20])
        out.append((ct, off, size))
    return out


def symtab(buf, off):
    if struct.unpack("<I", buf[off:off + 4])[0] != MH_MAGIC_64:
        return None
    ncmds = struct.unpack("<I", buf[off + 16:off + 20])[0]
    pos = off + 32
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack("<II", buf[pos:pos + 8])
        if cmd == LC_SYMTAB:
            return struct.unpack("<IIII", buf[pos + 8:pos + 24])
        pos += cmdsize
    return None


for ct, off, size in fat_slices(data):
    arch = {0x01000007: "x86_64", 0x0100000C: "arm64"}.get(ct, hex(ct))
    if arch != "x86_64":
        continue
    sym = symtab(data, off)
    if not sym:
        continue
    symoff, nsyms, stroff, strsize = sym
    strtab = data[off + stroff:off + stroff + strsize]

    exports: dict[str, int] = {}
    for i in range(nsyms):
        base = off + symoff + i * NLIST_64.size
        strx, ntype, nsect, _d, val = NLIST_64.unpack(data[base:base + NLIST_64.size])
        if not (ntype & N_EXT) or (ntype & N_SECT) != N_SECT:
            continue
        if strx >= strsize:
            continue
        end = strtab.find(b"\0", strx)
        name = strtab[strx:end if end > 0 else None].decode("latin-1")
        if "legacy90" in name:
            exports[name] = val

    print(f"slice {arch}: {len(exports)} _legacy90* exports\n")

    # group by base name (strip trailing precision suffix)
    PREC = re.compile(r"_(16s|32f|64f|32s|8u|16u)$")
    groups: dict[str, list[tuple[str, int]]] = {}
    for name, addr in exports.items():
        base = PREC.sub("", name)
        groups.setdefault(base, []).append((name, addr))

    for base in sorted(groups):
        members = sorted(groups[base])
        print(f"{base.split('legacy90')[-1]:34} x{len(members)}")
        codes = []
        for name, addr in members:
            code = data[off + addr:off + addr + PREFIX_BYTES]
            codes.append(code)
            prec = name[len(base):] or "(base)"
            print(f"    {prec:8} 0x{addr:X}  {code[:12].hex(' ')}")
        # compare entry prefixes
        if len(codes) > 1:
            common = 0
            for i in range(PREFIX_BYTES):
                firsts = {c[i] for c in codes if i < len(c)}
                if len(firsts) != 1:
                    break
                common += 1
            verdict = ("IDENTICAL entry" if common >= 11 else
                       f"divergent at +{common}")
            print(f"    -> {verdict}")

    # explicit absence checks
    print("\nabsence checks:")
    for probe in ("Interleave_64f", "VectorRamp_16s", "Deinterleave_64f"):
        present = any(probe in n for n in exports)
        print(f"  {probe:18} {'PRESENT' if present else 'absent'}")
