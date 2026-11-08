"""Is the JEV gate the reason fallback stops at lmstudio?

MEASURED so far:
    with lmstudio.base_url pointed at a dead port, chat() raises
        RuntimeError: all providers failed: lmstudio: HTTPConnectionPool(... port=9)
    The error lists ONLY lmstudio. nvidia and xpl never appear in the error chain.

Looking at the code, that can only happen if the loop `continue`s before attempting
them:

    if jev_gate and cfg["policy"].get("jev_gate") and route == "auto":
        if name != order[0] and not _jev_approve(...):
            errors.append(f"{name}: jev denied escalation")
            continue

If `_jev_approve` returns False, the provider is skipped AND an error is appended.
But the raised message does not contain "jev denied escalation", so that branch
appears NOT to have run -- which means the loop exited for another reason.

Two candidates:
  a  `chain` contains only lmstudio (order was truncated)
  b  an exception escaped the per-provider try and aborted the whole loop

Test both by inspecting the chain and the jev object directly.
"""
import json
import os
import sys

ROOT = r"C:\ABRASAX"
sys.path.insert(0, ROOT)

from agents.agents_hub import llm_router as R  # noqa: E402

print("=== 1. what chain would chat() build? ===")
import inspect
src = inspect.getsource(R.chat)
# find how `chain` is derived
for i, line in enumerate(src.splitlines(), 1):
    if "chain" in line and ("=" in line or "order" in line):
        print(f"  line {i}: {line.strip()}")

cfg = R._config()
order = cfg["policy"]["order"]
print(f"\n  policy order   : {order}")
print(f"  providers keys : {list(cfg['providers'])}")
print(f"  jev_gate policy: {cfg['policy'].get('jev_gate')}")

print("\n=== 2. the JEV object ===")
try:
    j = R._jev()
    print(f"  _jev() -> {type(j).__name__ if j is not None else 'None'}")
    if j is not None:
        for attr in ("yesno", "decide"):
            print(f"    has {attr}: {hasattr(j, attr)}")
        try:
            v = j.yesno("LLM route 'nvidia' requested. Approve this route?")
            print(f"    yesno(...) -> {v!r}  (bool={bool(v)})")
        except Exception as e:  # noqa: BLE001
            print(f"    yesno raised: {type(e).__name__}: {str(e)[:160]}")
            print("    -> chat() catches Exception and treats it as True (allow)")
    else:
        print("    None means approval is skipped (returns True)")
except Exception as e:  # noqa: BLE001
    print(f"  _jev() raised: {type(e).__name__}: {e}")

print("\n=== 3. simulate the loop decisions without network ===")
# reproduce the exact condition from the source
def would_attempt(name, routes_attempted):
    if name == order[0]:
        return True, "primary"
    try:
        ok = R._jev_approve(name, f"Primary '{order[0]}' unavailable.")
        return bool(ok), "jev said %r" % (ok,)
    except Exception as e:  # noqa: BLE001
        return False, f"jev raised {type(e).__name__}"


for name in order:
    allowed, why = would_attempt(name, [])
    print(f"  {name:10s} attempted={allowed}  ({why})")

print("\n=== 4. does _api_keys return anything for nvidia/xpl? ===")
for name in order:
    prov = cfg["providers"].get(name, {})
    keys = R._api_keys(prov)
    print(f"  {name:10s} keys={len(keys)}  base={R._base_url(prov)[:44]}")

print("\nRESULT: diagnosis only")
sys.exit(0)
