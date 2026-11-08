"""Find Unity Hub after winget reported 'Successfully installed'.

winget claims success but 'C:\\Program Files\\Unity Hub' does not exist and no
uninstall entry appeared. Search the whole of C: and J: for the binary and for
anything written in the last 15 minutes, so the claim can be checked against
reality instead of trusted.
"""
import os
import subprocess
import sys
import time

NAMES = ("unity hub.exe", "unityhub.exe")
ROOTS = ["C:\\Program Files", "C:\\Program Files (x86)",
         os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
         os.path.expandvars(r"%LOCALAPPDATA%"),
         os.path.expandvars(r"%APPDATA%"),
         "J:\\Unity"]

hits = []
for root in ROOTS:
    if not os.path.isdir(root):
        continue
    for dp, dn, fns in os.walk(root):
        # keep the walk bounded and fast
        depth = dp.count(os.sep) - root.count(os.sep)
        if depth > 4:
            dn[:] = []
            continue
        for fn in fns:
            if fn.lower() in NAMES:
                p = os.path.join(dp, fn)
                try:
                    hits.append((p, os.path.getsize(p)))
                except OSError:
                    hits.append((p, 0))

print("=== hub binaries ===")
for p, s in hits:
    print(f"  {p}  {s:,} bytes")
if not hits:
    print("  NONE")

print("\n=== files written in the last 15 min (Program Files + LocalAppData\\Programs) ===")
cut = time.time() - 15 * 60
recent = []
for root in ["C:\\Program Files", "C:\\Program Files (x86)",
             os.path.expandvars(r"%LOCALAPPDATA%\Programs")]:
    if not os.path.isdir(root):
        continue
    for dp, dn, fns in os.walk(root):
        depth = dp.count(os.sep) - root.count(os.sep)
        if depth > 3:
            dn[:] = []
            continue
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.getmtime(p) > cut:
                    recent.append(p)
            except OSError:
                pass
for p in recent[:30]:
    print("  " + p)
if not recent:
    print("  none")

sys.exit(0)
