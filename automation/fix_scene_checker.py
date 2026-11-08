"""Fix the component-block regex in verify_scene_structure.py.

The regex required the block to end with '--- ' lookahead but was anchored so it
could not traverse past the first few lines, so a perfectly valid component read as
"not found". The scene itself is fine -- verified by eye at lines 625-650.

Replace the fragile lookahead-regex with a straightforward document split: split
the file on the '--- !u!' banner, then find the document whose m_Script carries the
guid we want.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_scene_structure.py"
src = open(PATH, encoding="utf-8").read()

if "split_documents" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD_START = '# find the block and confirm the serialized fields\nblocks = re.findall('
idx = src.find(OLD_START)
if idx == -1:
    print("ANCHOR-NOT-FOUND: block-finding section")
    sys.exit(1)

# Find the end of the old block logic (up to the final RESULT print).
end_marker = 'print("\\nRESULT:"'
end_idx = src.find(end_marker, idx)
if end_idx == -1:
    print("ANCHOR-NOT-FOUND: RESULT print")
    sys.exit(1)

NEW = '''# find the block and confirm the serialized fields
# Split into documents on the Unity YAML banner. A regex with lookahead was too
# fragile here: it silently failed to match a valid component, which is a bug in
# the checker, not the scene.
parts = re.split(r"(?m)^--- !u!\\d+ &\\d+\\n", text)
blk = None
for part in parts:
    if ("guid: " + GUID) in part:
        blk = part
        break

if blk:
    print(f"[PASS] component document found ({len(blk)} bytes)")
    for field in ("baseUrl", "framesPerSecond", "exposure", "telemetryPerSecond"):
        has = re.search(r"(?m)^\\s+" + field + r":", blk) is not None
        print(f"  [{'PASS' if has else 'FAIL'}] field {field}")
        if not has:
            ok = False
    m = re.search(r"(?m)^\\s+baseUrl: (\\S+)", blk)
    if m:
        url_ok = m.group(1) == "http://127.0.0.1:9700"
        print(f"  [{'PASS' if url_ok else 'FAIL'}] baseUrl -> {m.group(1)}")
        if not url_ok:
            ok = False
    gm = re.search(r"(?m)^\\s+m_GameObject: \\{fileID: (\\d+)\\}", blk)
    if gm:
        go_ok = gm.group(1) in go_docs
        print(f"  [{'PASS' if go_ok else 'FAIL'}] m_GameObject {gm.group(1)} is a real GameObject")
        if not go_ok:
            ok = False
else:
    print("[FAIL] component document not found")
    ok = False

'''

src = src[:idx] + NEW + src[end_idx:]
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: component lookup now splits documents instead of regex lookahead")
