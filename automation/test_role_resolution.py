"""Test resolve_role on all 13 registered agents and show what each actually gets.

The audit flagged 10 of 13 agents as "NO DOCTRINE", matching role filenames to agent
names by substring. But resolve_role's own docstring says:

    "Order: registry routing key -> ROLES/*.md (id/stem/name) -> one of the 13
     in-process agents -> generic fallback. Never raises; an unknown role is a
     legitimate generic worker, not an error."

So a missing ROLES/*.md is NOT automatically a defect: the agent still resolves to an
in-process implementation. What matters is WHICH source each agent ends up on:

    registry    best  -- explicit routing key in registry.json
    roles       good  -- a doctrine markdown matched by id/stem/name
    agent       ok    -- an in-process agent with its own prompt
    fallback    weak  -- a generic worker, no specialised prompt

That distinction is the real finding, and it is measurable by calling the function.
"""
import json
import os
import sys

ROOT = r"C:\ABRASAX"
sys.path.insert(0, ROOT)

from abrasax.swarm_orchestrator import resolve_role  # noqa: E402

# get the registered agent names the same way the CLI does
import subprocess

PY = os.path.join(ROOT, "PYTHON", ".venv_gui", "Scripts", "python.exe")
r = subprocess.run([PY, "-m", "abrasax", "agents"], cwd=ROOT, capture_output=True,
                   text=True, timeout=120, stdin=subprocess.DEVNULL,
                   creationflags=0x08000000)
try:
    agents = json.loads(r.stdout)
except json.JSONDecodeError:
    agents = []

print(f"=== resolve_role() FOR {len(agents)} REGISTERED AGENTS ===\n")

sources = {}
rows = []
for a in agents:
    res = resolve_role(a)
    src = res.get("source", "?")
    sources[src] = sources.get(src, 0) + 1
    prompt_len = len(res.get("system") or "")
    rows.append((a, src, res.get("role_id"), res.get("agent_id"), prompt_len))

print(f"{'agent':24s} {'source':10s} {'role_id':10s} {'agent_id':12s} prompt")
for a, src, rid, aid, plen in rows:
    print(f"{a:24s} {src:10s} {str(rid or '-'):10s} {str(aid or '-'):12s} {plen}")

print("\n=== SOURCE DISTRIBUTION ===")
for s, n in sorted(sources.items(), key=lambda t: -t[1]):
    quality = {"registry": "explicit routing key",
               "roles": "doctrine markdown",
               "agent": "in-process agent",
               "fallback": "GENERIC -- no specialised prompt"}.get(s, s)
    print(f"  {s:10s} {n:3d}   {quality}")

weak = [a for a, src, *_ in rows if src == "fallback"]
print(f"\n  agents on generic fallback: {len(weak)}")
for a in weak:
    print(f"    {a}")

# prove a fallback still produces a usable prompt, not an empty string
if weak:
    sample = resolve_role(weak[0])
    print(f"\n  sample fallback prompt for '{weak[0]}':")
    print(f"    {repr(sample.get('system'))[:160]}")

# and that an explicit ROLES file DOES win when one exists
print("\n  control: resolve_role('02-code-reviewer')")
ctl = resolve_role("02-code-reviewer")
print(f"    source={ctl.get('source')} role_id={ctl.get('role_id')} "
      f"prompt_len={len(ctl.get('system') or '')}")

print("\nRESULT: report produced")
sys.exit(0)
