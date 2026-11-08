"""Add route='local' to llm_router.chat(): zero-cost only, fail closed.

Line 160 is:
    chain = order if route == "auto" else [route]

So route="local" currently looks up a provider literally named "local", finds
none, and fails with "unknown provider". This patch teaches the router about the
declared zero-cost chain and makes it impossible to silently escalate to a
billable provider.

Behaviour:
    auto  -> policy.order, unchanged (may reach nvidia/xpl, as today)
    local -> policy.zero_cost_order filtered to providers flagged local:true,
             and asserted to contain no remote provider
"""
import ast
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/AGENTS/agents_hub/llm_router.py")
BAK = TARGET.with_suffix(".py.bak-local-route")

OLD = '    chain = order if route == "auto" else [route]'

NEW = '''    if route == "local":
        # Zero-cost chain: only providers explicitly flagged local:true. A paid
        # provider must never be reachable from here, so assert rather than trust
        # the config file.
        policy = cfg["policy"]
        wanted = policy.get("zero_cost_order") or [
            n for n, p in cfg["providers"].items() if p.get("local")
        ]
        chain = [n for n in wanted
                 if cfg["providers"].get(n, {}).get("local")]
        paid = {"nvidia", "xpl"} & set(chain)
        if paid:
            raise RuntimeError(f"zero-cost route would reach paid providers: {sorted(paid)}")
        if not chain:
            raise RuntimeError("zero-cost route has no local provider configured")
    else:
        chain = order if route == "auto" else [route]'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if 'route == "local"' in src:
        print("already applied")
        return 0

    if OLD not in src:
        print("FAIL: chain anchor not found verbatim")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    src = src.replace(OLD, NEW, 1)
    ast.parse(src)
    TARGET.write_text(src, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
