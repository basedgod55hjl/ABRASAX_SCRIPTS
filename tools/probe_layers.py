"""What cognitive machinery exists today, and what is missing for Layer E?

Layers A-F are declared in the module docstrings:
    A sensor_registry   adapters
    B time_sync         clock
    C fusion            pose / state estimation
    D world_state       persistent truth
    F nervous_ui        renderer
    E ???               cognitive controller  <- NO MODULE DECLARES THIS

proposal.py calls itself a cognitive controller but is a review gate: it has no
loop, no cycle, no goals, no memory of its own. inventory the pieces that could
compose a controller, and identify the gap.
"""
import importlib
import inspect
import pathlib
import sys

sys.path.insert(0, r"C:\ABRASAX")

CANDIDATES = [
    "proposal", "decision", "experiments", "prediction", "brain",
    "swarm_orchestrator", "selfedit", "build_loop", "scope", "kcal",
    "world_health", "skills_index", "memory", "bus", "agents_api",
]

print("=== modules that could contribute to a cognitive controller ===\n")
for name in CANDIDATES:
    try:
        m = importlib.import_module(f"abrasax.{name}")
    except Exception as e:
        print(f"  {name:<20} IMPORT FAILED: {type(e).__name__}")
        continue
    doc = (inspect.getdoc(m) or "").splitlines()
    first = doc[0] if doc else "(no docstring)"
    public = [n for n in dir(m) if not n.startswith("_")]
    layer = ""
    import re
    mm = re.search(r"\(Layer ([A-F])\)", first)
    if mm:
        layer = f" [Layer {mm.group(1)}]"
    print(f"  {name:<20}{layer}")
    print(f"    {first[:110]}")
    print(f"    public: {', '.join(public[:10])}")

print("\n=== layer claims ===")
for name in CANDIDATES + ["sensor_registry", "time_sync", "fusion",
                          "world_state", "nervous_ui"]:
    try:
        m = importlib.import_module(f"abrasax.{name}")
    except Exception:
        continue
    d = inspect.getdoc(m) or ""
    import re
    mm = re.search(r"Layer ([A-F])", d)
    if mm:
        print(f"  Layer {mm.group(1)}: abrasax.{name}")

print("\n=== the gap ===")
print("  A controller needs: a loop, a state it owns, goals, and a way to act.")
print("  proposal.py has none of those - it is a permission check invoked")
print("  per-call. decision.py is a one-shot arithmetic verdict. experiments.py")
print("  stores hypotheses. Nothing composes them into a cycle.")
