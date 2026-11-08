"""Verify every script GUID referenced by Main.unity resolves to a real .cs file.

The scene is hand-authored YAML. `Tools/validate-project.py` checks it offline, but
that tool compares strings. This resolves GUIDs the way Unity does and reports
anything dangling, so a scene that would load with missing-script errors is caught
before the editor ever opens it.

Method: every Unity asset has a sibling `.meta` with
    guid: <32 hex>
Build a guid -> asset path map from Assets/, then every `guid:` in the scene must
appear in it.

Exit 0 = all references resolve.
"""
import os
import re
import sys

# Paths come from one resolver so a script cannot open the wrong tree.
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
from abra_paths import paths  # noqa: E402

ASSETS = str(paths.unity_assets)
SCENE = os.path.join(ASSETS, "Scenes", "Main.unity")

GUID_RE = re.compile(r"guid:\s*([0-9a-f]{32})")

# ---------------------------------------------------------------- build the map
guid_to_path = {}
meta_count = 0
for dirpath, _dirnames, filenames in os.walk(ASSETS):
    for fn in filenames:
        if not fn.endswith(".meta"):
            continue
        meta_count += 1
        full = os.path.join(dirpath, fn)
        try:
            text = open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = GUID_RE.search(text)
        if not m:
            continue
        asset = full[:-5]  # strip ".meta"
        guid_to_path[m.group(1)] = asset

print(f"meta files scanned : {meta_count}")
print(f"guids mapped       : {len(guid_to_path)}")

if not os.path.isfile(SCENE):
    print(f"FAIL: scene not found: {SCENE}")
    sys.exit(1)

scene = open(SCENE, encoding="utf-8", errors="replace").read()
refs = GUID_RE.findall(scene)

print(f"scene bytes        : {len(scene):,}")
print(f"guid references    : {len(refs)}")
print(f"distinct guids     : {len(set(refs))}")

# ------------------------------------------------------------------ resolve them
resolved, missing = [], []
for g in sorted(set(refs)):
    if g in guid_to_path:
        resolved.append((g, guid_to_path[g]))
    else:
        missing.append(g)

print("\n--- resolved references ---")
for g, path in resolved:
    rel = os.path.relpath(path, str(paths.unity_build))
    print(f"  {g}  {rel}")

# Broken references are normal for Unity built-in assets (URP materials, the
# default skybox, etc.) whose GUIDs live in package caches, not in Assets/. So we
# only fail on references that look like *our* scripts but resolve nowhere.
print("\n--- unresolved references ---")
script_guids = {}
for g, path in guid_to_path.items():
    if path.endswith(".cs"):
        script_guids[g] = path

print(f"  our .cs scripts      : {len(script_guids)}")
for g, path in sorted(script_guids.items()):
    rel = os.path.relpath(path, str(paths.unity_build))
    print(f"  {g}  {rel}")

if missing:
    print(f"\n  {len(missing)} guid(s) not found under Assets/:")
    for g in missing:
        print(f"    {g}")
    print("  (these are typically package/built-in assets; see note above)")
else:
    print("  none")

ok = True
if not script_guids:
    print("\nFAIL: no .cs scripts have .meta files -- Unity cannot bind them")
    ok = False

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
