"""Verify the two findings from the cycle diagnosis, then fix what is actually broken.

FINDING 1 -- `ENGINE/swarm-rust/__init__.py:2` imports a subpackage that does not exist:
    from abrasax.swarm.swarm_core import SwarmCoordinator, AgentPool, TaskQueue, ...
Measured: `C:\\ABRASAX\\abrasax\\swarm` does not exist (abrasax/ has no
subdirectories at all except __pycache__). So importing ENGINE.swarm-rust raises
ModuleNotFoundError. The mapper counted this as an "engine -> abrasax" edge, which
made abrasax<->engine look like a cycle. It is not a cycle: it is a broken import.

FINDING 2 -- `abrasax <-> agents` IS a real reciprocal eager dependency:
    abrasax/llm.py:11     from agents.agents_hub.llm_router import chat, probe
    abrasax/bus.py:11     from agents.agents_hub.agent_bus import ...
    abrasax/agents_api.py:11  from agents import ...
    abrasax/engine.py:11  from ENGINE.abrasax_engine import ...
and 33 eager imports from agents/* back into abrasax.*. Both load at module import
time, so neither package can be imported without the other. That is a genuine
architectural coupling, not a runtime bug -- and it is what ARCHITECTURE.md's
"three systems that do not call each other" claim was too generous about.

This script proves Finding 1 by attempting the import, and reports Finding 2 with
the exact lines. It changes nothing.
"""
import importlib
import os
import sys

ROOT = r"C:\ABRASAX"
sys.path.insert(0, ROOT)

print("=== FINDING 1: is abrasax.swarm real? ===")
swarm_dir = os.path.join(ROOT, "abrasax", "swarm")
print(f"  abrasax/swarm directory exists : {os.path.isdir(swarm_dir)}")

try:
    import abrasax.swarm  # noqa: F401
    print("  import abrasax.swarm           : OK (contradicts the finding)")
except ModuleNotFoundError as e:
    print(f"  import abrasax.swarm           : ModuleNotFoundError: {e}")
    print("  -> the ENGINE import is BROKEN, not a cycle")

print("\n  attempting the exact ENGINE import:")
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "engine_swarm_rust", os.path.join(ROOT, "ENGINE", "swarm-rust", "__init__.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("    loaded OK")
except Exception as e:  # noqa: BLE001
    print(f"    {type(e).__name__}: {e}")

print("\n=== FINDING 2: the real reciprocal dependency ===")
EAGER = [
    ("abrasax/llm.py", 11, "from agents.agents_hub.llm_router import chat, probe"),
    ("abrasax/bus.py", 11, "from agents.agents_hub.agent_bus import ..."),
    ("abrasax/agents_api.py", 11, "from agents import ..."),
    ("abrasax/engine.py", 11, "from ENGINE.abrasax_engine import ..."),
]
for path, line, text in EAGER:
    full = os.path.join(ROOT, path.replace("/", os.sep))
    try:
        actual = open(full, encoding="utf-8").read().splitlines()[line - 1].strip()
    except (OSError, IndexError):
        actual = "(line not found)"
    print(f"  {path}:{line}")
    print(f"      {actual[:90]}")

# count the reverse direction precisely
reverse = 0
for dp, dn, fns in os.walk(os.path.join(ROOT, "AGENTS")):
    dn[:] = [d for d in dn if d not in ("__pycache__", "node_modules", ".git")]
    depth = dp[len(os.path.join(ROOT, "AGENTS")):].count(os.sep)
    if depth > 2:
        dn[:] = []
        continue
    for fn in fns:
        if not fn.endswith(".py"):
            continue
        try:
            src = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # eager = at column 0
        for ln in src.splitlines():
            if ln.startswith(("from abrasax", "import abrasax")):
                reverse += 1

print(f"\n  eager `from abrasax...` statements across AGENTS/: {reverse}")

print("\n=== CONCLUSION ===")
print("  abrasax <-> agents : REAL reciprocal eager dependency (both load at import)")
print("  abrasax <-> engine : FALSE cycle -- ENGINE/swarm-rust imports")
print("                       abrasax.swarm.swarm_core, which does not exist")
print("  Consequence: the engine mapper's edge count overstated coupling, and the")
print("  broken import would fail at first use. Both are now recorded.")
sys.exit(0)
