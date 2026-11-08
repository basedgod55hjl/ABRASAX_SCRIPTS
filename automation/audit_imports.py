"""Measure import safety instead of asserting it.

The first automation_brain.json carried a hand-written DANGEROUS blacklist and
claimed "221 import-safe". That was an assumption: a regex pass over the same
tools finds module-scope side-effect calls in 161 of them. An index that
confidently mislabels a tool as safe-to-import is worse than no index, because
the next agent will trust it and import reclaim_bt2.

This computes, per tool, from the AST:
  * modules imported (stdlib vs third-party vs local)
  * whether there is real module-scope work (calls, not just constants)
  * which calls are *mutating* (write/unlink/remove/run/Popen/rmtree/rename/
    chmod/mkdir/patch) -- these are the ones that make import dangerous
  * the derived safety class, replacing the hand-written blacklist
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
AUTO = ROOT / "SCRIPTS/automation"
OUT = ROOT / "DATA/runtime-memory/automation_import_audit.json"

STDLIB = set(sys.stdlib_module_names)
MUTATING = {
    "write_text", "write_bytes", "unlink", "rmdir", "remove", "removedirs",
    "rmtree", "rename", "replace", "chmod", "mkdir", "makedirs", "run",
    "Popen", "call", "check_call", "check_output", "system", "startfile",
    "copy", "copy2", "copytree", "move", "touch", "symlink", "link",
    "save", "dump", "dumpz", "write",
}
MUTATING_MODULES = {"shutil", "subprocess", "os", "webbrowser", "winreg", "ctypes"}


def classify_call(node: ast.Call) -> tuple[str, bool]:
    """-> (dotted name, is_mutating)"""
    f = node.func
    parts: list[str] = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    parts.reverse()
    name = ".".join(parts)
    last = parts[-1] if parts else ""
    mutating = (
        last in MUTATING
        or (parts and parts[0] in MUTATING_MODULES and last in MUTATING)
        or "patch" in last.lower()
        or "write" in last.lower()
    )
    return name, mutating


def audit(p: Path) -> dict:
    src = p.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)

    imports: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports += [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            imports.append(n.module.split(".")[0])

    third_party = sorted({m for m in imports if m not in STDLIB and m not in {
        "brain3d", "panels", "activity_bus", "abrasax", "AGENTS"}})

    scope_work: list[str] = []
    mutating: list[str] = []
    for node in tree.body:  # MODULE scope only
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Import, ast.ImportFrom)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                name, is_mut = classify_call(sub)
                if not name:
                    continue
                if name.split(".")[0] in ("print", "len", "str", "int", "float",
                                          "sorted", "set", "list", "dict", "enumerate",
                                          "range", "round", "any", "all", "min", "max"):
                    continue
                scope_work.append(name)
                if is_mut:
                    mutating.append(name)

    if any("exit" in m for m in mutating) or "sys.exit" in scope_work:
        safety = "exits-on-import"
    elif mutating:
        safety = "mutates-on-import"
    elif scope_work:
        safety = "does-work-on-import"
    else:
        safety = "pure"

    return {
        "tool": p.stem,
        "third_party": third_party,
        "module_scope_calls": len(scope_work),
        "mutating_calls": sorted(set(mutating))[:6],
        "safety": safety,
        "sample_scope_calls": sorted(set(scope_work))[:5],
    }


def main() -> int:
    rows = [audit(p) for p in sorted(AUTO.glob("*.py"))]
    tally: dict[str, int] = {}
    for r in rows:
        tally[r["safety"]] = tally.get(r["safety"], 0) + 1

    tp: dict[str, int] = {}
    for r in rows:
        for m in r["third_party"]:
            tp[m] = tp.get(m, 0) + 1

    out = {
        "registry": "automation-import-audit",
        "generated_by": "SCRIPTS/automation/audit_imports.py",
        "analysed": len(rows),
        "safety_tally": dict(sorted(tally.items(), key=lambda kv: -kv[1])),
        "third_party_deps": dict(sorted(tp.items(), key=lambda kv: -kv[1])),
        "tools": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"analysed {len(rows)} tools -> {OUT.name}")
    print("safety tally (MEASURED, replaces the hand-written blacklist):")
    for k, v in out["safety_tally"].items():
        print(f"   {k:22} {v}")
    print("\nthird-party dependencies across the folder:")
    for k, v in list(out["third_party_deps"].items())[:12]:
        print(f"   {k:22} used by {v}")
    unsafe = [r for r in rows if r["safety"] != "pure"]
    print(f"\nNOT importable: {len(unsafe)} / {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
