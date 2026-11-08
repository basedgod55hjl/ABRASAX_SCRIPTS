"""Raw string search across the whole binary -- bypass the (suspect) symtab parse.

The previous probe read only the LC_SYMTAB string table and found ~120 strings per
binary, which is implausibly small. Symbol names may be stripped, but the
LITERAL STRINGS the claim depends on (the reg.xml path, selector names, FPC
banner strings) live in __TEXT/__cstring/__const and are found by a plain byte
search, not by symbol table parsing.

Searches every byte of each binary for each probe string.
"""
from __future__ import annotations

from pathlib import Path
# DEAD PATH (sirch): original C:\Users\sirch\_WORK\fl_unpack dataset has no local equivalent on this host.

BASE = Path(r"C:\abrasax\_DEAD_PATH\fl_unpack\Library\Audio\Plug-Ins\VST"
            r"\FL Studio VSTi.vst\Contents")
SHARED = BASE / "Resources" / "Shared"

PROBES = [
    # claim 1: FPC 3.2.3
    b"FPC", b"FreePascal", b"Free Pascal", b"3.2.3", b"fpc_",
    b"FPC_INITIALIZEUNITS", b"SYSTEM_$$_",
    # claim 2: Delphi / VCL
    b"TForm", b"TApplication", b"TWinControl", b"TCustomForm", b"Vcl.",
    b"Delphi", b"Embarcadero", b"Classes.pas", b"System.pas",
    # claim 3: registry -> reg.xml
    b"reg.xml", b"Image-Line", b"/Preferences/", b"RegOpenKey", b"HKEY_",
    b"RegQueryValueEx", b"RegSetValueEx",
    # claim 4: NSDragging mapping
    b"NSDragging", b"draggingSession", b"NSDraggingInfo", b"draggingSource",
    b"pasteboard", b"NSPasteboard",
    # claim 5: OLE
    b"DoDragDrop", b"RegisterDragDrop", b"IDropTarget", b"OleInitialize",
    b"ole32", b"OLE32",
    # claim 6: Win32 shim
    b"GetProcAddress", b"LoadLibrary", b"CreateWindowEx", b"SetWindowLong",
    b"GetMessage", b"DispatchMessage", b"user32", b"kernel32", b"win32",
    b"Win32",
    # sanity: things that SHOULD be present
    b"__TEXT", b"mach_header", b"FL Studio", b"vstplugin",
    b"Il", b"ImageLine",
]

targets = [BASE / "MacOS" / "vstplugin",
           SHARED / "ILTools_x64.dylib",
           SHARED / "libwinbridge_x64.dylib"]

for p in targets:
    if not p.exists():
        continue
    blob = p.read_bytes()
    print(f"\n{'=' * 70}\n{p.name}  ({len(blob):,} bytes)")
    found, missing = [], []
    for probe in PROBES:
        n = blob.count(probe)
        (found if n else missing).append((probe, n))
    print("  FOUND:")
    for probe, n in found:
        print(f"    {probe.decode('ascii', 'replace'):24} x{n}")
    print(f"  not found ({len(missing)}): " +
          ", ".join(x[0].decode("ascii", "replace") for x in missing[:14]))
