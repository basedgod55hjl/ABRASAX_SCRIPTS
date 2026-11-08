#!/usr/bin/env python3
"""fix_unity_state_vector.py -- leg_reach_7 is a flat array, and the parser said so was impossible.

Measured 2026-11-01 after the depth fix in fix_unity_compute_kernels.py:
    LOGS/brain_state.json:  spine_points -> 9 rows x 7 dims   (nested, parsed correctly now)
                            leg_reach_7  -> [1.0, 0.484, 1.0, 0.4752, 0.4885, 0.4668, 0.7098]
    ParseMatrix("leg_reach_7") -> 0 rows, because it only ever collected *nested* rows
    (`\\[[^\\]]*\\]`). A flat vector therefore came back empty, BrainState7D.Valid stayed false,
    and the component kept running on SyntheticState() while claiming to read the canonical file.

This teaches ParseMatrix the flat case: when the captured body contains no '[', the whole body
is one row. Re-run Unity's self-test after this and state_valid flips to true.

Run: python SCRIPTS/fix_unity_state_vector.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

CS = Path(r"C:\UnityProjects\ABRASAX-Brain") / "Assets" / "BrainUI" / "Scripts" / "Spine7DCompute.cs"

OLD = """            string body = start >= 0 && i > start ? json.Substring(start, i - start) : "";
            foreach (Match row in Regex.Matches(body, "\\\\[[^\\\\]]*\\\\]"))"""

NEW = """            string body = start >= 0 && i > start ? json.Substring(start, i - start) : "";
            if (!body.Contains("["))
            {
                // A flat vector ("leg_reach_7": [a, b, c, ...]) has no nested rows, so the
                // nested-row pass below found nothing and the whole vector came back empty.
                var flat = new List<float>();
                foreach (Match num in Regex.Matches(body, "-?\\\\d+(?:\\\\.\\\\d+)?(?:[eE][+-]?\\\\d+)?"))
                    flat.Add(float.Parse(num.Value, CultureInfo.InvariantCulture));
                if (flat.Count > 0) rows.Add(flat.ToArray());
                return rows.ToArray();
            }
            foreach (Match row in Regex.Matches(body, "\\\\[[^\\\\]]*\\\\]"))"""

MARK = "A flat vector"


def main() -> int:
    if not CS.exists():
        print(f"FAIL  missing {CS}")
        return 1
    text = CS.read_text(encoding="utf-8-sig")
    applied = MARK in text
    if "--check" in sys.argv:
        print(("PASS " if applied else "FAIL ") + f"flat-vector parsing={applied}")
        return 0 if applied else 1
    if applied:
        print("already patched: ParseMatrix flat vectors")
        return 0
    if OLD not in text:
        print("FAIL  ParseMatrix body anchor not found")
        return 1
    bak = CS.with_suffix(".cs.bak-flatvec")
    if not bak.exists():
        bak.write_text(text, encoding="utf-8")
    CS.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched ParseMatrix: flat vectors are one row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
