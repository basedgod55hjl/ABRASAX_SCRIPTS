"""Structural gate for the ABRASAX UI brain.

Answers one question the test suite doesn't: are the six worker modules still
one coherent system? Tests prove behaviour; this proves *shape* — every module
the contract names exists, exports the names the contract names, the overlay
only calls APIs that actually exist, and nobody has smuggled in a dependency
the runtime doesn't have.

Exit 0 = coherent, 1 = drift. Prints a per-check table.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
FB = ROOT / "ENGINE/floating_brain"
CONTRACT = FB / "ABRAX_LAYER_CONTRACT.md"

# name -> (file, required top-level names). Source: ABRAX_LAYER_CONTRACT.md
REQUIRED = {
    "flywire_assets.py": [
        "FlyWireGraph", "load_graph", "save_npz", "load_npz", "export_obj",
        "neuropil_anchors",
    ],
    "brain3d.py": ["Brain3D", "build_vertices", "load_field", "telemetry",
                   "build_wire_vertices"],
    "panels.py": ["PanelManager"],
    "activity_bus.py": ["ActivityBus", "sample_system", "read_brain_state",
                        "read_llm_tail"],
    "live_transformer.py": ["LiveTransformer"],
}
# LiveTransformer lives in a sibling package dir per the contract.
EXTRA_DIRS = [ROOT / "ENGINE/model"]

FORBIDDEN_IMPORTS = {
    "websockets", "fastapi", "uvicorn", "starlette", "requests", "aiohttp",
    "pydantic", "flask", "django", "psutil", "noise", "perlin",
}

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def find_module(fname: str) -> Path | None:
    for d in [FB, *EXTRA_DIRS]:
        p = d / fname
        if p.exists():
            return p
    return None


def top_level_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


def all_defs(tree: ast.Module) -> set[str]:
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def imported_roots(tree: ast.Module) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                mods.add(node.module.split(".")[0])
    return mods


def main() -> int:
    check("contract present", CONTRACT.exists(), str(CONTRACT))
    if CONTRACT.exists():
        text = CONTRACT.read_text(encoding="utf-8", errors="replace")
        check("contract: activity schema",
              '"state": "idle|thinking|tool|memory|alert|high_load"' in text)
        check("contract: 'no third-party deps' rule",
              "Do NOT add third-party dependencies" in text)

    trees: dict[str, ast.Module] = {}
    for fname, names in REQUIRED.items():
        p = find_module(fname)
        check(f"{fname}: exists", p is not None, str(p or "MISSING"))
        if not p:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
        except SyntaxError as exc:
            check(f"{fname}: parses", False, f"{exc.msg} line {exc.lineno}")
            continue
        check(f"{fname}: parses", True)
        trees[fname] = tree
        have = top_level_names(tree)
        missing = [n for n in names if n not in have]
        check(f"{fname}: contract API", not missing, "missing " + ",".join(missing) if missing else "all present")

    # no forbidden imports anywhere in the UI tree
    bad: list[str] = []
    for p in list(FB.glob("*.py")) + [d / f for d in EXTRA_DIRS for f in ("live_transformer.py",)]:
        if not p.exists():
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for mod in imported_roots(tree) & FORBIDDEN_IMPORTS:
            bad.append(f"{p.name}:{mod}")
    check("no forbidden imports", not bad, ",".join(bad)[:180])

    # overlay must only call brain3d APIs that exist
    ov = FB / "imgui_overlay.py"
    b3 = trees.get("brain3d.py")
    if ov.exists() and b3 is not None:
        src = ov.read_text(encoding="utf-8", errors="replace")
        known = all_defs(b3)
        called = set(re.findall(r"(?:brain3d|b3)\.(\w+)\s*\(", src))
        ghost = sorted(c for c in called if c not in known)
        check("overlay->brain3d API", not ghost,
              ("calls nonexistent " + ",".join(ghost)) if ghost else f"{len(called)} calls resolve")

    # shared ActivityBus section names must match the contract schema
    bus = trees.get("activity_bus.py")
    if bus is not None:
        src = (find_module("activity_bus.py") or Path()).read_text(encoding="utf-8", errors="replace")
        for section in ("brain", "transformer", "llm", "tools", "memory", "system"):
            check(f"activity section '{section}'", section in src)

    # the UI brain index itself
    brain_json = ROOT / "DATA/runtime-memory/ui_brain.json"
    if brain_json.exists():
        try:
            b = json.loads(brain_json.read_text(encoding="utf-8"))
            check("ui_brain.json: loads", True, f"digest {b.get('digest')}")
            check("ui_brain.json: canonical>0", b["corpus"]["canonical"] > 0,
                  f"{b['corpus']['canonical']} entries")
            check("ui_brain.json: sdk ok", b["sdk"]["all_required_present"])
            check("ui_brain.json: probe ran", (b["sdk"].get("probe_run") or {}).get("rc") == 0)
            paths = [s["path"] for s in b["skills"]]
            dead = [p for p in paths if not Path(p).exists()]
            check("ui_brain.json: skill paths live", not dead, f"{len(dead)} dead links")
        except (json.JSONDecodeError, KeyError) as exc:
            check("ui_brain.json: loads", False, str(exc))
    else:
        check("ui_brain.json: loads", False, "missing")

    width = max(len(n) for n, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
