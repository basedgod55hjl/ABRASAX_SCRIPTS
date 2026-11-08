"""Add a VISION panel to the overlay, fed by the ui_steer ledger.

Why: the steering layer writes what the vision/unity GGUFs concluded, but
nothing on screen showed it, so the loop was write-only. This makes the HUD the
consumer: frame, model, verdict, age.

Idempotent; refuses to apply twice.
"""
from __future__ import annotations

import sys
from pathlib import Path

P = Path(r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py")
src = P.read_text(encoding="utf-8")

if 'pid == "vision"' in src:
    sys.exit("already patched")

# 1. panel spec: put VISION opposite BUILD
anchor_spec = '                ("build", "BUILD / TOOLS", (0.6, 1.0, 0.0), (0, 0), (210, 112)),'
if anchor_spec not in src:
    sys.exit("panel spec anchor not found")
src = src.replace(
    anchor_spec,
    anchor_spec + '\n                ("vision", "VISION", (-0.6, 1.0, 0.0), (0, 0), (210, 118)),',
    1,
)

# 2. content provider, inserted before the build branch
anchor_build = '        if pid == "build":'
if anchor_build not in src:
    sys.exit("build branch anchor not found")
vision_branch = '''        if pid == "vision":
            return vision_panel()

'''
src = src.replace(anchor_build, vision_branch + anchor_build, 1)

# 3. the loader: reads the steering state off disk, cached at 2 Hz
anchor_state = '    def panel_content(pid: str):'
if anchor_state not in src:
    sys.exit("panel_content anchor not found")
loader = '''    _vision_cache = {"t": 0.0, "row": {}}

    def vision_panel() -> dict:
        """Newest ui_steer verdict. Disk read at most twice a second."""
        now_v = time.time()
        if now_v - _vision_cache["t"] < 0.5:
            return _vision_cache["row"]
        _vision_cache["t"] = now_v
        row = {"model": "none", "verdict": "no steering data", "age": "-"}
        try:
            import json as _json
            p = (Path(__file__).resolve().parent / ".." / ".." / "DATA" / "runtime-memory" / "vision_steer_state.json").resolve()
            if p.exists():
                st = _json.loads(p.read_text(encoding="utf-8"))
                last = st.get("last") or {}
                verdict = (last.get("unity_plan") or last.get("vision_audit") or "").strip()
                model = last.get("unity_model") or last.get("vision_model") or "none"
                ts = last.get("ts") or ""
                age = "-"
                if ts:
                    try:
                        from datetime import datetime, timezone
                        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        age = f"{int((datetime.now(timezone.utc) - then).total_seconds())}s"
                    except ValueError:
                        age = "-"
                row = {"model": str(model)[:20],
                       "verdict": (verdict.replace("\\n", " ")[:140] or "model returned nothing"),
                       "age": age}
        except (OSError, ValueError):
            row = {"model": "err", "verdict": "state unreadable", "age": "-"}
        _vision_cache["row"] = row
        return row

'''
src = src.replace(anchor_state, loader + anchor_state, 1)

P.write_text(src, encoding="utf-8")
print(f"patched {P.name}: VISION panel added ({len(src)} chars)")
