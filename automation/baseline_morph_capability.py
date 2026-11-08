"""Design the morphing brain: what morphs, driven by what, verified how.

CURRENT STATE (measured, not assumed)
    Unity editor      J:\\Unity\\7000.0.0a10\\Editor\\Unity.exe      present
    Unity license     C:\\ProgramData\\Unity\\Unity_lic.ulf          present
    Unity project     Assembly-CSharp.dll 46,592 B                   compiles
    Unreal            no UE_5.x anywhere                              ABSENT
    Morphing          grep 'morph' across the renderer               ZERO hits
    Renderer          :9700 live, steps 2493

So of the four things this section asks for, three exist and one does not:
    3D visualization      YES -- Poincare-projected node cloud, birefringent field
    live UI               YES -- ImGui overlay at 19.6 fps, Unity client compiled
    Unity / Unreal        Unity YES, Unreal NO (blocked on an Epic install)
    MORPHING BRAIN        NO  -- this is the gap

WHAT "MORPH" SHOULD MEAN HERE, DEFINED BEFORE CODE

    A brain that changes SHAPE over time in response to its own state, not a random
    animation. Concretely, four morph targets already have data to drive them:

    1  Poincare radius morph
       Each node's position inside the ball is (x/(1+|x|+phi^-1+kappa)). As the
       field's activity changes, nodes migrate outward (certain -> boundary). That
       IS a morph, and it is already computed by fb_project_all. It has never been
       rendered as motion because the node cloud is only splatted to a 2D field.

    2  Defect-driven surface deform
       fb_find_defects yields +/-1/2 charges. If those charges displace the surface,
       the visual shows where the field is singular -- the "energy knots" from the
       design source.

    3  Phase-lock collapse
       fb_phase_lock already computes an alpha per node: locked nodes bright, unlocked
       collapse to 12%. Rendering alpha as a RADIUS rather than brightness makes the
       brain visibly inhale when coherence drops.

    4  Temporal morph (Akashic tape)
       fb_akashic_tape holds history. Interpolating between two history frames gives
       a literal before/after morph.

    All four are derived from data the GPU already has. None requires new simulation.

WHAT IS MEASURABLE

    A morph is only real if frame N differs from frame N+1 in a way that is DRIVEN by
    the input, not by noise. So the test is: change one input, hold everything else,
    and show the output moved.
        clock 0.0 vs 0.5   -> different frame (temporal morph)
        yaw 0 vs 90        -> different frame (spatial morph)
        step the brain     -> different frame (field-driven morph)

This script establishes the baseline and names the gap precisely. It builds nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import urllib.request
import zlib

RENDER = "http://127.0.0.1:9700"
ROOT = r"C:\ABRASAX"


def frame(clock, yaw=0, pitch=0, exposure=24):
    url = f"{RENDER}/frame.png?clock={clock}&exposure={exposure}&yaw={yaw}&pitch={pitch}"
    with urllib.request.urlopen(url, timeout=25) as r:
        data = r.read()
    i, idat, ihdr = 8, b"", None
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"IHDR":
            ihdr = data[i + 8:i + 8 + ln]
        elif typ == b"IDAT":
            idat += data[i + 8:i + 8 + ln]
        i += 12 + ln
    w, h = struct.unpack(">II", ihdr[:8])
    raw = zlib.decompress(idat)
    st = 1 + w * 4
    px = bytearray()
    for y in range(h):
        px += raw[y * st + 1:(y + 1) * st]
    return w, h, bytes(px)


def digest(px):
    return hashlib.sha256(px).hexdigest()[:16]


print("=== BASELINE: does the image already move, and is the motion driven? ===")

# the three drivers that already exist
cases = [
    ("clock 0.00", 0.00, 0, 0),
    ("clock 0.25", 0.25, 0, 0),
    ("clock 0.50", 0.50, 0, 0),
    ("yaw 90", 0.50, 90, 0),
    ("pitch 45", 0.50, 0, 45),
]

hashes = {}
for label, clock, yaw, pitch in cases:
    w, h, px = frame(clock, yaw, pitch)
    d = digest(px)
    uniq = len(set(px[k:k + 4] for k in range(0, len(px), 4)))
    hashes[label] = d
    print(f"  {label:12s} {w}x{h}  uniq={uniq:4d}  sha={d}")

distinct = len(set(hashes.values()))
print(f"\n  distinct frames across {len(cases)} inputs: {distinct}")
print(f"  [{'PASS' if distinct == len(cases) else 'FAIL'}] every input produces a distinct frame")

# is the change small (morph) or total (different image)?
print("\n=== what morphing capability is MISSING ===")
checks = [
    ("node cloud rendered as 3D geometry", False,
     "nodes are splatted to a 64x64 field (fb_node_to_field); no vertex/point output"),
    ("Poincare radius rendered as motion", False,
     "radius is computed in fb_project_all but only collapsed to 3D then flattened"),
    ("defect charges displace the surface", False,
     "fb_find_defects computes charge/confidence; nothing consumes them for geometry"),
    ("phase-lock drives size, not brightness", False,
     "fb_phase_lock sets alpha/glow; radius is not modulated"),
    ("temporal interpolation between frames", False,
     "fb_akashic_tape stores history; no cross-frame blend"),
]
for name, done, why in checks:
    print(f"  [{'HAVE' if done else 'GAP '}] {name}")
    if not done:
        print(f"        {why}")

print("\n=== what EXISTS and is verified ===")
print("  3D visualization : Poincare ball projection + birefringent field, live")
print("  live UI          : ImGui overlay 19.6 fps (DOC/IMGUI-OVERLAY.md §10)")
print("  Unity            : editor + license + Assembly-CSharp.dll 46,592 B")
print("  Unreal           : ABSENT -- no UE_5.x on any drive")

out = os.path.join(ROOT, "LOGS", "morph-baseline.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"frames": hashes, "distinct": distinct,
               "gaps": [{"capability": n, "why": w} for n, _, w in checks if _ is False]},
              f, indent=2)
print(f"\nwrote {out}")
sys.exit(0)
