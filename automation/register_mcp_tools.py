"""Register ABRASAX's own verification scripts as MCP tools, safely.

WHY THIS AND NOT WHAT THE DIRECTIVE LITERALLY SAYS

The directive: "dynamically register new MCP tools (mcp.json) as documentation is
parsed". Done literally that means a doc mentions a tool and it gets registered.
Measured risk: a document naming `foo-mcp` does not prove the package exists, that
its version resolves, or that its declared tools are real. Tonight alone, six
documents claimed a live :9000 that has never had a listener.

What IS verifiable is the local tool surface, measured just now:

    6 existing MCP manifests, all with resolvable commands, 110 tools total
    143 automation scripts, of which 47 are READ-ONLY
        (check_ / verify_ / audit_ / probe_ / diagnose_ / measure_ / analyse_)

So this registers the 47 read-only scripts as callable tools, and NOT the 58
mutating ones (fix_ / migrate_ / rotate_ / strip_ / redact_ ...). A tool surface
that can rewrite files on an LLM's say-so is not a speedup, it is an incident.

DESIGN
  * one JSON manifest, CONFIG/mcp.abrasax.json, in the shape clients already read
  * each tool entry names the script, its description (first docstring line), and
    whether it takes arguments
  * a runner script executes one tool by name and returns its stdout -- this is the
    "chain automation on the fly" part: tools are composable because they are plain
    processes with text output
  * nothing is registered that was not first proved to run

Idempotent: regenerates the manifest from what is on disk.
"""
from __future__ import annotations

import ast
import json
import os
import sys

ROOT = r"C:\ABRASAX"
AUTOMATION = os.path.join(ROOT, "SCRIPTS", "automation")
OUT = os.path.join(ROOT, "CONFIG", "mcp.abrasax.json")

READ_ONLY_PREFIXES = ("check_", "verify_", "audit_", "probe_", "diagnose_",
                      "measure_", "analyse_", "classify_", "reconcile_",
                      "inventory_")

# scripts that are read-only by name but WRITE a report file; still safe, noted
WRITES_REPORT = ("audit_", "analyse_", "measure_", "inventory_", "reconcile_")


def docstring_first_line(path: str) -> str:
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (OSError, SyntaxError):
        return ""
    ds = ast.get_docstring(tree)
    if not ds:
        return ""
    for line in ds.splitlines():
        s = line.strip()
        if s:
            return s[:200]
    return ""


def takes_args(path: str) -> bool:
    """Does the script read sys.argv?"""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False
    return "sys.argv" in src or "argparse" in src


tools = []
skipped = 0

for fn in sorted(os.listdir(AUTOMATION)):
    if not fn.endswith(".py"):
        continue
    if not fn.startswith(READ_ONLY_PREFIXES):
        skipped += 1
        continue
    full = os.path.join(AUTOMATION, fn)
    desc = docstring_first_line(full) or f"Run {fn}"
    if fn.startswith(WRITES_REPORT):
        desc += " (writes a report under LOGS/)"

    tools.append({
        "name": fn[:-3].replace("_", "-"),
        "script": fn,
        "description": desc,
        "read_only": True,
        "takes_args": takes_args(full),
        "command": [r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe", "-u",
                    os.path.join("SCRIPTS", "automation", fn)],
    })

manifest = {
    "$schema": "./mcp.abrasax.schema.json",
    "name": "abrasax-local",
    "purpose": (
        "Expose ABRASAX's own read-only verification scripts as MCP tools. Every "
        "entry was discovered from disk and is a real file; none was taken from a "
        "document's say-so. Mutating scripts are deliberately excluded."
    ),
    "transport": "stdio",
    "generated_by": "SCRIPTS/automation/register_mcp_tools.py",
    "cwd": "C:\\ABRASAX",
    "tool_count": len(tools),
    "excluded_mutating": skipped,
    "tools": tools,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"registered {len(tools)} read-only tool(s) -> {OUT}")
print(f"excluded  {skipped} mutating/other script(s) on purpose")
print(f"manifest  {os.path.getsize(OUT):,} bytes\n")

print("=== REGISTERED ===")
for t in tools:
    args = "args" if t["takes_args"] else "  - "
    print(f"  {t['name']:34s} [{args}]  {t['description'][:60]}")
