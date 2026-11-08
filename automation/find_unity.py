"""Locate Unity Hub and any Unity editor on this machine, wherever they are.

Earlier checks only looked at 'C:\\Program Files\\Unity Hub'. The license client
and five Hub processes were running from 10:25 AM, so a Hub binary exists
somewhere. This searches the plausible install roots and reports the truth.
"""
import os
import sys

CANDIDATES = [
    r"C:\Program Files\Unity Hub",
    r"C:\Program Files (x86)\Unity Hub",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Unity Hub"),
    os.path.expandvars(r"%LOCALAPPDATA%\UnityHub"),
    os.path.expandvars(r"%APPDATA%\UnityHub"),
    os.path.expandvars(r"%LOCALAPPDATA%\Unity"),
    r"C:\Program Files\Unity",
    r"C:\Program Files (x86)\Unity",
]

print("=== candidate roots ===")
for c in CANDIDATES:
    ex = os.path.exists(c)
    n = 0
    if ex:
        for _dp, _dn, fns in os.walk(c):
            n += len(fns)
    print(f"{'OK ' if ex else '-- '} {c}  files={n}")

print("\n=== hub binaries found ===")
found = []
for root in CANDIDATES:
    if not os.path.isdir(root):
        continue
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            low = fn.lower()
            if low in ("unity hub.exe", "unityhub.exe") or low == "unity.exe":
                p = os.path.join(dp, fn)
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    sz = 0
                found.append((p, sz))
                print(f"  {p}  {sz:,} bytes")

if not found:
    print("  none")

print("\n=== result ===")
hub = [f for f in found if "hub" in f[0].lower()]
editor = [f for f in found if f[0].lower().endswith("unity.exe")]
print(f"Unity Hub binaries : {len(hub)}")
print(f"Unity editor exes  : {len(editor)}")
sys.exit(0)
