"""Confirm Assembly-CSharp.dll really contains the BrainUI types.

A 35 KB DLL proves *something* compiled. The claim under test is that Unity
compiled the project's own scripts -- BrainClient, BrainHUD, BrainFieldBinder --
not merely the package assemblies.

Reads the .NET metadata string heap directly (no external tools, no Mono.Cecil).
Type and method names live as length-prefixed UTF-8 strings in the #Strings heap,
so a substring scan of the file is sufficient and honest: if the name is not in
the image, the type was not compiled into it.

Exit 0 = all expected types present.
"""
import os
import struct
import sys

# Paths come from one resolver so a script cannot open the wrong tree.
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
from abra_paths import paths  # noqa: E402

DLL = str(paths.unity_dll)

EXPECTED = [
    "BrainClient",
    "BrainHUD",
    "BrainFieldBinder",
    "FloatingBrainRenderer",
    "RenderTelemetry",
    "Brain",
]

if not os.path.isfile(DLL):
    print(f"FAIL: not found: {DLL}")
    sys.exit(1)

data = open(DLL, "rb").read()
print(f"file      : {DLL}")
print(f"size      : {len(data):,} bytes")

# PE / CLI sanity
if data[:2] != b"MZ":
    print("FAIL: not a PE image")
    sys.exit(1)
pe_off = struct.unpack_from("<I", data, 0x3C)[0]
if data[pe_off:pe_off + 4] != b"PE\0\0":
    print("FAIL: missing PE signature")
    sys.exit(1)
print(f"PE header : 0x{pe_off:X}  valid")

# .NET metadata signature BSJB
bsjb = data.find(b"BSJB")
print(f"BSJB      : {'0x%X' % bsjb if bsjb > 0 else 'MISSING'}")
if bsjb < 0:
    print("FAIL: no CLI metadata -- not a managed assembly")
    sys.exit(1)

print("\n--- expected type names in the string heap ---")
ok = True
for name in EXPECTED:
    present = name.encode("ascii") in data
    print(f"[{'PASS' if present else 'FAIL'}] {name}")
    if not present:
        ok = False

# Also show every Brain*-prefixed identifier we can see, for a real cross-check.
print("\n--- identifiers containing 'Brain' ---")
found = set()
needle = b"Brain"
i = 0
while True:
    i = data.find(needle, i)
    if i < 0:
        break
    j = i
    while j > 0 and (65 <= data[j - 1] <= 90 or 97 <= data[j - 1] <= 122
                     or 48 <= data[j - 1] <= 57 or data[j - 1] == 95):
        j -= 1
    k = i
    while k < len(data) and (65 <= data[k] <= 90 or 97 <= data[k] <= 122
                             or 48 <= data[k] <= 57 or data[k] == 95):
        k += 1
    if k - j >= 5:
        found.add(data[j:k].decode("ascii", "replace"))
    i += 1

for name in sorted(found):
    print("  " + name)

# References to UntyWebRequest prove the manifest fix took effect.
print("\n--- UnityWebRequest module reference ---")
has_uwr = b"UnityWebRequest" in data
print(f"[{'PASS' if has_uwr else 'NOTE'}] UnityWebRequest referenced in the image: {has_uwr}")

print("\nRESULT:", "PASS -- BrainUI compiled into Assembly-CSharp.dll" if ok else "FAIL")
sys.exit(0 if ok else 1)
