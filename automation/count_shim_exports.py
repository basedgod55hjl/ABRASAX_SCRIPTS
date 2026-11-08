"""Count libwinbridge's exported functions -- the one unverified figure.

The claim under test says the Win32 shim exposes "32 functions". Everything else
in the provenance claim has been reconciled against the binaries; this number has
not.

Exports live in the LC_DYSYMTAB external-relocation/export range, not in
LC_SYMTAB's local symbols. This reads LC_SYMTAB + LC_DYSYMTAB and extracts the
external-defined symbols (nlist n_type & N_EXT, N_SECT), then groups them.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

P = Path(r"C:\abrasax\_DEAD_PATH\fl_unpack\Library\Audio\Plug-Ins\VST"
         r"\FL Studio VSTi.vst\Contents\Resources\Shared\libwinbridge_x64.dylib")

FAT_MAGIC = 0xCAFEBABE
MH_MAGIC_64 = 0xFEEDFACF
LC_SYMTAB = 0x2
LC_DYSYMTAB = 0xB
N_EXT, N_SECT, N_UNDF, N_ABS, N_INDR = 0x01, 0x0E, 0x0, 0x2, 0xA
NLIST_64 = struct.Struct("<IBBHQ")   # n_strx, n_type, n_sect, n_desc, n_value


def slices(fh):
    if struct.unpack(">I", fh.read(4))[0] != FAT_MAGIC:
        return []
    n = struct.unpack(">I", fh.read(4))[0]
    return [(struct.unpack(">iiIII", fh.read(20))) for _ in range(n)]


def analyse(fh, off) -> None:
    fh.seek(off)
    hdr = fh.read(32)
    if struct.unpack("<I", hdr[:4])[0] != MH_MAGIC_64:
        print(f"  @{off:#x}: not MH_MAGIC_64")
        return
    cputype = struct.unpack("<i", hdr[4:8])[0]
    arch = {0x01000007: "x86_64", 0x0100000C: "arm64"}.get(cputype, hex(cputype))
    ncmds = struct.unpack("<I", hdr[16:20])[0]
    pos, sym = off + 32, None
    for _ in range(ncmds):
        fh.seek(pos)
        raw = fh.read(8)
        if len(raw) < 8:
            break
        cmd, cmdsize = struct.unpack("<II", raw)
        if cmd == LC_SYMTAB:
            fh.seek(pos + 8)
            sym = struct.unpack("<IIII", fh.read(16))
        pos += cmdsize

    print(f"\n--- slice {arch} @{off:#x}")
    if not sym:
        print("  no LC_SYMTAB")
        return
    symoff, nsyms, stroff, strsize = sym
    fh.seek(stroff)
    strtab = fh.read(strsize)
    fh.seek(symoff)
    raw_syms = fh.read(nsyms * NLIST_64.size)

    exported, undeclared, local = [], [], 0
    for i in range(nsyms):
        chunk = raw_syms[i * NLIST_64.size:(i + 1) * NLIST_64.size]
        if len(chunk) < NLIST_64.size:
            break
        strx, ntype, nsect, _desc, _val = NLIST_64.unpack(chunk)
        if strx >= len(strtab):
            continue
        end = strtab.find(b"\0", strx)
        name = strtab[strx:end if end > 0 else None].decode("ascii", "replace")
        if not name:
            continue
        is_ext = bool(ntype & N_EXT)
        typ = ntype & N_SECT
        if is_ext and typ == N_SECT:
            exported.append(name)
        elif typ == N_UNDF and is_ext:
            undeclared.append(name)
        else:
            local += 1

    print(f"  nsyms={nsyms}  exported(T,ext)={len(exported)}  "
          f"undefined(U)={len(undeclared)}  local/other={local}")
    print("  exported names:")
    for n in sorted(exported)[:80]:
        print(f"    {n}")
    # heuristics for the shim
    win = [n for n in exported if re.search(
        r"(Reg|Window|Message|Drag|Drop|Clipboard|Cursor|Key|Mouse|Menu|File|"
        r"Path|String|Thread|Handle|Dll|Proc|Module|Desktop|System)", n, re.I)]
    print(f"\n  win32-ish exported: {len(win)}")
    for n in sorted(win):
        print(f"    {n}")


with P.open("rb") as fh:
    for ct, _s, off, _sz, _a in slices(fh):
        analyse(fh, off)
