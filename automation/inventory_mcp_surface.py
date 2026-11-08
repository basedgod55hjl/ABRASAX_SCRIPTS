"""Find what MCP tools can be registered for real, before registering anything.

The directive is to "dynamically register new MCP tools (mcp.json) as documentation
is parsed". Taken literally, that means: the doc index mentions a tool, so add it.
That is unsafe -- a document mentioning `foo-mcp` does not mean the package exists,
that its version resolves, or that its tools are what the doc claims.

So first, measure what is actually registerable on THIS machine:

  1  which MCP servers already have a manifest in MCP/servers/
  2  which of those have a resolvable command (node, npx, python on PATH)
  3  what the ABRASAX helper scripts could expose as tools (the 142 automation
     scripts are the real, local, verifiable tool surface)
  4  what an mcp.json would need to look like for a client to consume it

Nothing is registered here. This is the inventory a registration step would act on.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = r"C:\ABRASAX"
SERVERS = os.path.join(ROOT, "MCP", "servers")
AUTOMATION = os.path.join(ROOT, "SCRIPTS", "automation")

print("=== 1. EXISTING MCP MANIFESTS ===")
manifests = []
for name in sorted(os.listdir(SERVERS)):
    d = os.path.join(SERVERS, name)
    mf = os.path.join(d, "server.json")
    if not os.path.isfile(mf):
        continue
    try:
        m = json.load(open(mf, encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  {name:22s} BAD JSON: {e}")
        continue
    manifests.append((name, m))
    cmd = m.get("command", "")
    exists = os.path.exists(cmd) or shutil.which(os.path.basename(cmd) or cmd)
    print(f"  {name:22s} transport={m.get('transport', '?'):6s} "
          f"cmd_ok={bool(exists)!s:5s} tools={len(m.get('tools', []))}")

print(f"\n  {len(manifests)} manifest(s)")

print("\n=== 2. TOOLCHAIN AVAILABILITY ===")
for exe in ("node", "npx", "python", "dotnet", "git"):
    p = shutil.which(exe)
    print(f"  {exe:8s} {'-> ' + p if p else 'NOT ON PATH'}")

print("\n=== 3. LOCAL TOOL SURFACE: the automation scripts ===")
scripts = sorted(f for f in os.listdir(AUTOMATION) if f.endswith(".py"))
# classify by what they can honestly offer as a tool
checkable, mutating, internal = [], [], []
for fn in scripts:
    full = os.path.join(AUTOMATION, fn)
    try:
        text = open(full, encoding="utf-8", errors="replace").read(4000)
    except OSError:
        continue
    low = fn.lower()
    if low.startswith(("check_", "verify_", "audit_", "probe_", "diagnose_",
                       "analyse_", "measure_", "classify_", "reconcile_")):
        checkable.append(fn)
    elif low.startswith(("fix_", "migrate_", "rotate_", "attach_", "retire_",
                         "mark_", "harden_", "strip_", "redact_", "correct_",
                         "wire_", "add_", "tune_", "move_", "make_")):
        mutating.append(fn)
    else:
        internal.append(fn)

print(f"  total         : {len(scripts)}")
print(f"  read-only tools (check/verify/audit/probe/diagnose/measure/analyse): "
      f"{len(checkable)}")
print(f"  mutating tools (fix/migrate/rotate/attach/...): {len(mutating)}")
print(f"  other         : {len(internal)}")

print("\n  read-only candidates (safe to expose as MCP tools):")
for fn in checkable:
    print(f"    {fn}")

print("\n=== 4. WHAT A CONSUMABLE mcp.json NEEDS ===")
print("  A single file listing servers with command + args, in the shape the")
print("  clients on this machine already read. Existing example on disk:")
example = r"C:\ABRASAX\CONFIG\source-config\mcp.json"
if os.path.exists(example):
    try:
        d = json.load(open(example, encoding="utf-8"))
        print(f"    {example}")
        print(f"    top-level keys: {list(d)[:6]}")
        for k in list(d)[:2]:
            print(f"    {k}: {json.dumps(d[k])[:160]}")
    except (json.JSONDecodeError, OSError) as e:
        print(f"    unreadable: {e}")
else:
    print("    (no example found)")

# readiness verdict
ready = [n for n, m in manifests
         if os.path.exists(m.get("command", "")) or shutil.which("npx")]
print(f"\n=== READINESS ===")
print(f"  manifests whose command resolves : {len(ready)}/{len(manifests)}")
print(f"  local read-only tools available  : {len(checkable)}")
sys.exit(0)
