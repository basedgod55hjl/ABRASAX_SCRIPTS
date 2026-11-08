#!/usr/bin/env python3
"""fix_unity_compute_kernels.py -- two defects the editor self-test found on its first run.

Measured 2026-11-01 (LOGS/unity_compute_test.log, unity_compute_selftest.json):
    Shader error in 'Spine7D': incorrect number of arguments to numeric-type constructor
      at kernel CSGeodesic at Assets/BrainUI/Resources/Spine7D.compute(52) (on dx12)
    Spine7D.compute: Kernel at index (0) is invalid
    ... same for CSField ... "non_zero": 0, "lit": 0

D1 -- the shader never compiled. Line 52 is `norm7()`:
        float3 h = q.xyz;  return length(float4(p.xyz, h));   // float4(float3,float3) = 6 args
     `poincare3()` had the same mistake one function below. Both kernels were invalid, so both
     dispatches were no-ops and the field stayed at its clear colour. Nothing in the project
     had ever dispatched them, so nothing had ever failed.

D2 -- the state parser could never see the real file. `ParseMatrix` started its bracket depth
     at 0 although the outer '[' had already been consumed by the regex, so it stopped at the
     end of the FIRST row: spine_points came back as 1 row instead of 9, `Valid` was false, and
     the component silently ran on SyntheticState() forever. The self-test reported
     "state_valid": false while LOGS/brain_state.json was perfectly good.

Run: python SCRIPTS/fix_unity_compute_kernels.py [--check]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT = Path(r"C:\UnityProjects\ABRASAX-Brain")
SHADER = PROJECT / "Assets" / "BrainUI" / "Resources" / "Spine7D.compute"
CS = PROJECT / "Assets" / "BrainUI" / "Scripts" / "Spine7DCompute.cs"

NORM_OLD = """// 7D norm
float norm7(float4 p, float4 q)
{
    float3 h = q.xyz;
    return length(float4(p.xyz, h));
}"""

NORM_NEW = """// 7D norm: dims 0..3 live in p, dims 4..6 in q.xyz. A float4 cannot be built from two
// float3s, which is what used to be here and what dx12 rejected.
float norm7(float4 p, float4 q)
{
    return sqrt(dot(p, p) + dot(q.xyz, q.xyz));
}"""

POINCARE_OLD = """    float4 x = float4(p.xyz, q.xyz);
    float n = length(x);"""

POINCARE_NEW = """    // 4D slice of the 7D point: xyz of the control point + the radial term from dim 4.
    float4 x = float4(p.xyz, q.x);
    float n = length(x);"""

PARSE_OLD = """            var m = Regex.Match(json, "\\"" + key + "\\"\\\\s*:\\\\s*\\\\[");
            if (!m.Success) return rows.ToArray();
            int depth = 0, start = -1, i = m.Index + m.Length;
            // scan the outer [...] tracking nested brackets
            for (; i < json.Length; i++)
            {
                char c = json[i];
                if (c == '[') { if (depth == 0) start = i + 1; depth++; }
                else if (c == ']') { depth--; if (depth == 0 && start >= 0) break; }
            }"""

PARSE_NEW = """            var m = Regex.Match(json, "\\"" + key + "\\"\\\\s*:\\\\s*\\\\[");
            if (!m.Success) return rows.ToArray();
            // The regex consumed the outer '['; the body starts immediately after it and the
            // depth is already 1. Starting at 0 (as this did) ended the scan at the close of
            // the first nested row, so a 9x7 matrix came back as a single row.
            int depth = 1, i = m.Index + m.Length;
            int start = i;
            for (; i < json.Length; i++)
            {
                char c = json[i];
                if (c == '[') depth++;
                else if (c == ']') { depth--; if (depth == 0) break; }
            }"""


def main() -> int:
    shader = SHADER.read_text(encoding="utf-8", errors="replace")
    cs = CS.read_text(encoding="utf-8-sig")

    applied = (
        "sqrt(dot(p, p) + dot(q.xyz, q.xyz))" in shader
        and "float4 x = float4(p.xyz, q.x);" in shader
        and "int depth = 1, i = m.Index + m.Length;" in cs
    )
    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"unity kernels fixed={applied}")
        return 0 if applied else 1
    if applied:
        print("already patched: Spine7D.compute + Spine7DCompute.ParseMatrix")
        return 0

    notes = []
    if NORM_OLD in shader:
        shader = shader.replace(NORM_OLD, NORM_NEW, 1)
        notes.append("norm7: 7D dot-product norm")
    if POINCARE_OLD in shader:
        shader = shader.replace(POINCARE_OLD, POINCARE_NEW, 1)
        notes.append("poincare3: valid float4 constructor")
    if not notes and "sqrt(dot(p, p)" not in shader:
        print("FAIL  shader anchors not found (file changed?)")
        return 1
    if "sqrt(dot(p, p)" in shader:
        SHADER.write_text(shader, encoding="utf-8")

    if PARSE_OLD in cs:
        cs = cs.replace(PARSE_OLD, PARSE_NEW, 1)
        notes.append("ParseMatrix: depth starts at the outer bracket")
        bak = CS.with_suffix(".cs.bak-parsefix")
        if not bak.exists():
            bak.write_text(CS.read_text(encoding="utf-8-sig"), encoding="utf-8")
        CS.write_text(cs, encoding="utf-8")
    elif "int depth = 1, i = m.Index + m.Length;" not in cs:
        print("FAIL  ParseMatrix anchor not found")
        return 1

    # Backups must not live under Assets/: Unity imported the .bak as a real asset.
    moved = []
    stash = PROJECT / "_backups"
    stash.mkdir(exist_ok=True)
    # .meta files are handled with their asset; a glob list is a snapshot, so re-check
    # existence instead of trusting it (the first pass proved that the hard way).
    for junk in [p for p in PROJECT.glob("Assets/**/*.bak-*") if p.suffix != ".meta"]:
        if not junk.exists():
            continue
        shutil.move(str(junk), str(stash / junk.name))
        meta = junk.with_suffix(junk.suffix + ".meta")
        if meta.exists():
            meta.unlink()
        moved.append(junk.name)
    if moved:
        notes.append("moved out of Assets/: " + ", ".join(moved))

    for n in notes:
        print("  + " + n)
    print("patched unity compute kernels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
