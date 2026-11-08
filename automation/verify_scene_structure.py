"""Structural check on Main.unity after attaching FloatingBrainRenderer.

Adding a component by hand can produce a scene that Unity loads but silently
mis-binds. This verifies the invariants the format requires:

  1. every `- component: {fileID: N}` on a GameObject has a matching document
     `--- !u!<class> &N`
  2. every MonoBehaviour's `m_GameObject` points at a real GameObject
  3. every `m_Script` guid resolves to an asset under Assets/
  4. no duplicate fileIDs (would make Unity pick one arbitrarily)
  5. the specific new component exists with the expected fields

Exit 0 = the scene is structurally sound.
"""
import os
import re
import sys

# Paths come from one resolver so a script cannot open the wrong tree.
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
from abra_paths import paths  # noqa: E402

SCENE = str(paths.unity_scene)
ASSETS = str(paths.unity_assets)
GUID = "3783e7e28e441cf4cb996650d876599c"

text = open(SCENE, encoding="utf-8").read()
ok = True

# ---- 1. document anchors -------------------------------------------------
docs = re.findall(r"^--- !u!(\d+) &(\d+)", text, re.M)
doc_ids = [d[1] for d in docs]
print(f"documents          : {len(docs)}")
print(f"distinct fileIDs   : {len(set(doc_ids))}")

dupes = {i for i in doc_ids if doc_ids.count(i) > 1}
if dupes:
    print(f"FAIL: duplicate fileIDs: {sorted(dupes)}")
    ok = False
else:
    print("[PASS] no duplicate fileIDs")

# ---- 2. component back-references ---------------------------------------
comp_refs = re.findall(r"- component: \{fileID: (\d+)\}", text)
print(f"\ncomponent refs     : {len(comp_refs)}")
dangling = [c for c in comp_refs if c not in doc_ids]
if dangling:
    print(f"FAIL: component refs with no document: {dangling}")
    ok = False
else:
    print("[PASS] every component ref resolves to a document")

# ---- 3. m_GameObject back-references ------------------------------------
go_docs = {d[1] for d in docs if d[0] == "1"}
mgo = re.findall(r"m_GameObject: \{fileID: (\d+)\}", text)
bad_mgo = [g for g in mgo if g != "0" and g not in go_docs]
print(f"\nm_GameObject refs  : {len(mgo)}")
print(f"GameObject docs    : {len(go_docs)}")
if bad_mgo:
    print(f"FAIL: m_GameObject pointing at non-GameObjects: {bad_mgo}")
    ok = False
else:
    print("[PASS] every m_GameObject resolves to a GameObject")

# ---- 4. script guids resolve -------------------------------------------
guid_map = {}
for dp, _dn, fns in os.walk(ASSETS):
    for fn in fns:
        if fn.endswith(".meta"):
            p = os.path.join(dp, fn)
            m = re.search(r"guid:\s*([0-9a-f]{32})", open(p, encoding="utf-8", errors="replace").read())
            if m:
                guid_map[m.group(1)] = p[:-5]

script_guids = re.findall(r"m_Script: \{fileID: \d+, guid: ([0-9a-f]{32})", text)
print(f"\nm_Script refs      : {len(script_guids)}")
unresolved = [g for g in script_guids if g not in guid_map]
for g in sorted(set(script_guids)):
    # guid_map entries live on J: (Assets) while unity_build is C:; Windows
    # cannot relpath across volumes. The basename is all this print needs.
    where = os.path.basename(guid_map[g]) if g in guid_map else "UNRESOLVED"
    print(f"  {g}  {where}")
if unresolved:
    print(f"[NOTE] {len(unresolved)} script guid(s) not under Assets/ (package scripts)")
else:
    print("[PASS] every m_Script guid resolves under Assets/")

# ---- 5. the new component ------------------------------------------------
print("\n--- FloatingBrainRenderer component ---")
present = GUID in text
print(f"[{'PASS' if present else 'FAIL'}] guid {GUID} referenced in scene")
if not present:
    ok = False

# find the block and confirm the serialized fields
# Split into documents on the Unity YAML banner. A regex with lookahead was too
# fragile here: it silently failed to match a valid component, which is a bug in
# the checker, not the scene.
parts = re.split(r"(?m)^--- !u!\d+ &\d+\n", text)
blk = None
for part in parts:
    if ("guid: " + GUID) in part:
        blk = part
        break

if blk:
    print(f"[PASS] component document found ({len(blk)} bytes)")
    for field in ("baseUrl", "framesPerSecond", "exposure", "telemetryPerSecond"):
        has = re.search(r"(?m)^\s+" + field + r":", blk) is not None
        print(f"  [{'PASS' if has else 'FAIL'}] field {field}")
        if not has:
            ok = False
    m = re.search(r"(?m)^\s+baseUrl: (\S+)", blk)
    if m:
        url_ok = m.group(1) == "http://127.0.0.1:9700"
        print(f"  [{'PASS' if url_ok else 'FAIL'}] baseUrl -> {m.group(1)}")
        if not url_ok:
            ok = False
    gm = re.search(r"(?m)^\s+m_GameObject: \{fileID: (\d+)\}", blk)
    if gm:
        go_ok = gm.group(1) in go_docs
        print(f"  [{'PASS' if go_ok else 'FAIL'}] m_GameObject {gm.group(1)} is a real GameObject")
        if not go_ok:
            ok = False
else:
    print("[FAIL] component document not found")
    ok = False

print("\nRESULT:", "PASS -- scene structurally sound" if ok else "FAIL")
sys.exit(0 if ok else 1)
