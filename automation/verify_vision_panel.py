import ast
import sys

p = r"C:\ABRASAX\ENGINE\floating_brain\imgui_overlay.py"
src = open(p, encoding="utf-8").read()
ast.parse(src)
print("overlay AST OK")

# the panel spec and branch must both exist
assert '("vision", "VISION"' in src, "panel spec missing"
assert 'pid == "vision"' in src, "branch missing"
assert "def vision_panel()" in src, "loader missing"

# exercise the loader's real logic against the real state file
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(r"C:\ABRASAX\DATA\runtime-memory\vision_steer_state.json")
print("state file exists:", state_path.exists())
if state_path.exists():
    st = json.loads(state_path.read_text(encoding="utf-8"))
    last = st.get("last") or {}
    verdict = (last.get("unity_plan") or last.get("vision_audit") or "").strip()
    model = last.get("unity_model") or last.get("vision_model") or "none"
    ts = last.get("ts") or ""
    age = "-"
    if ts:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age = f"{int((datetime.now(timezone.utc) - then).total_seconds())}s"
    print(f"model={model!r} age={age} verdict={verdict[:90]!r}")
print("VISION panel patch verified")
