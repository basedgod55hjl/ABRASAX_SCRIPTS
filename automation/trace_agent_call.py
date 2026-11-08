"""Close the causal chain: which alias does each agent request, and does it 400?

ESTABLISHED
  _pick_model('reason')    -> deepseek/deepseek-r1-0528-qwen3-8b   engine aborts
  _pick_model('reasoning') -> prism-ml/bonsai-27b                  works
  reasoning_effort and max_tokens=2048 are both ACCEPTED by lmstudio (all 200).
  So build_loop's edit is innocent; the 400 comes from the model behind the alias.

REMAINING QUESTION
  Does run_live() actually pass a model alias for code-reviewer / test-engineer, or
  does it leave model=None? If None, the router picks gemma-4-e2b-uncensored-hauhaucs-aggressive and the
  request must succeed -- which contradicts the ledger.

So read agents_api.run_live and see what model it forwards, then reproduce the exact
call for one agent and capture the real 400 body.
"""
import inspect
import json
import sys

sys.path.insert(0, r"C:\ABRASAX")

print("=== how does run_live choose a model? ===")
from abrasax import agents_api

src = inspect.getsource(agents_api.run_live)
for i, line in enumerate(src.splitlines(), 1):
    s = line.strip()
    if any(k in s for k in ("model", "route", "alias", "ask(", "run_live", "def ")):
        print(f"  {i:3d}: {s[:110]}")

print("\n=== reproduce the agent call that fails ===")
try:
    r = agents_api.run_live(
        "code-reviewer",
        "Review this one line of Python: x = 1",
        route="auto",
    )
    ok = (r or {}).get("ok")
    print(f"  ok={ok}")
    print(f"  model={(r or {}).get('model')}")
    print(f"  routed_via={(r or {}).get('routed_via')}")
    content = (r or {}).get("output") or (r or {}).get("content") or ""
    print(f"  output={str(content)[:120]!r}")
    err = (r or {}).get("error")
    if err:
        print(f"  error={str(err)[:300]}")
except Exception as e:  # noqa: BLE001
    print(f"  raised {type(e).__name__}: {str(e)[:400]}")

print("\n=== and with an explicit working model ===")
try:
    r2 = agents_api.run_live(
        "code-reviewer",
        "Review this one line of Python: x = 1",
        route="auto",
        model="gemma-4-e2b-uncensored-hauhaucs-aggressive",
    )
    print(f"  ok={(r2 or {}).get('ok')}")
    print(f"  model={(r2 or {}).get('model')}")
    content = (r2 or {}).get("output") or (r2 or {}).get("content") or ""
    print(f"  output={str(content)[:160]!r}")
except Exception as e:  # noqa: BLE001
    print(f"  raised {type(e).__name__}: {str(e)[:300]}")

print("\n=== what the agent prompt looks like ===")
try:
    from abrasax.swarm_orchestrator import resolve_role
    role = resolve_role("code-reviewer")
    print(f"  source={role.get('source')} role_id={role.get('role_id')}")
    print(f"  prompt={str(role.get('system'))[:200]!r}")
except Exception as e:  # noqa: BLE001
    print(f"  {type(e).__name__}: {e}")
