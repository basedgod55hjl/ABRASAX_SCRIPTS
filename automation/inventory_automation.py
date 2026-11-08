"""Collect every SCRIPTS/automation tool and report what belongs in a brain.

Before writing a single file into ABRASAX, establish ground truth:
  * which automation scripts are session work vs pre-existing
  * which are reusable tools vs one-off debug probes (those should NOT be brained)
  * which already have tests, and which are silently untested
  * do all of them at least COMPILE (py_compile) -- a syntax error in this folder
    is a landmine for anyone who runs it later
"""
from __future__ import annotations

import ast
import py_compile
import re
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
AUTO = ROOT / "SCRIPTS/automation"
TESTS = ROOT / "TESTS/python"

SESSION = {
    "build_ui_brain", "patch_brain_redaction", "wire_activity_bus", "fs_diff",
    "rank_ui_skills", "extract_ui_skills", "ui_brain_gate", "overlay_windows",
    "capture_overlay", "overlay_foreground", "overlay_detached", "add_vision_panel",
    "verify_vision_panel", "gguf_probe", "gguf_trace", "maya_gate",
    "maya_all_tests", "maya_triage", "maya_entrypoint_repro", "maya_fix_entrypoint",
    "config_audit", "fix_providers_note", "measure_bt", "reclaim_bt",
    "reclaim_bt2", "bt_progress", "zip_stream", "probe_unity_installer",
    "disk_top", "disk_targets", "boblight_conf", "boblight_check", "find_boblight",
    "supervisor_overlay", "overlay_health", "maya_pytest",
    "maya_entrypoint_diag", "maya_entrypoint_proof", "maya_entrypoint_isolate",
    "maya_entrypoint_identity", "py_stdout_probe", "_repair_gguf",
}
# one-off forensics: kept for the record, but not "brain" material
ONE_OFF = {
    "maya_entrypoint_diag", "maya_entrypoint_proof", "maya_entrypoint_isolate",
    "maya_entrypoint_identity", "py_stdout_probe", "_repair_gguf", "bt_progress",
    "gguf_trace", "measure_bt", "disk_top", "find_boblight",
}

files = sorted(AUTO.glob("*.py"))
print(f"automation scripts: {len(files)}")

syntax_bad = []
rows = []
for p in files:
    stem = p.stem
    try:
        py_compile.compile(str(p), doraise=True)
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except (py_compile.PyCompileError, SyntaxError) as exc:
        syntax_bad.append(f"{p.name}: {str(exc)[:80]}")
        continue
    doc = (ast.get_docstring(tree) or "").splitlines()
    has_main = any(
        isinstance(n, ast.If) and "__main__" in ast.dump(n) for n in tree.body
    )
    rows.append({
        "name": stem, "bytes": p.stat().st_size,
        "doc": doc[0][:90] if doc else "",
        "main": has_main, "session": stem in SESSION, "one_off": stem in ONE_OFF,
    })

print(f"py_compile failures: {len(syntax_bad)}")
for b in syntax_bad[:10]:
    print("   ", b)

# which have a matching test?
test_src = "\n".join(
    t.read_text(encoding="utf-8", errors="replace") for t in TESTS.glob("test_*.py")
)
tested = {r["name"] for r in rows if re.search(rf"\b{re.escape(r['name'])}\b", test_src)}
print(f"scripts referenced by a test: {len(tested)}/{len(rows)}")

sess = [r for r in rows if r["session"]]
print(f"\nsession scripts: {len(sess)}")
print(f"  reusable (brain material): {len([r for r in sess if not r['one_off']])}")
print(f"  one-off forensics:         {len([r for r in sess if r['one_off']])}")
print(f"  with __main__ entry:       {len([r for r in sess if r['main']])}")
print(f"  covered by a test:         {len([r for r in sess if r['name'] in tested])}")

print("\n=== reusable session tools")
for r in sorted(sess, key=lambda r: r["name"]):
    if r["one_off"]:
        continue
    mark = "T" if r["name"] in tested else " "
    print(f" [{mark}] {r['name']:28} {r['bytes']:>6} B  {r['doc']}")
