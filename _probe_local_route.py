"""_probe_local_route.py - where does route='auto' actually go, and how fast?

    python SCRIPTS/_probe_local_route.py ["prompt"]

Prints provider/routed_via/model and elapsed seconds. With the local-first
policy and at least one local provider up, `provider` must be local and no
paid endpoint may appear in the log line.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.agents_hub import llm_router as R  # noqa: E402
from abrasax import autonomy  # noqa: E402


def main(argv: list[str]) -> int:
    prompt = argv[0] if argv else "Reply with exactly: ROUTER-LOCAL-OK"
    state = autonomy.snapshot()
    print(f"mode={state['mode']} paid_allowed={state['paid_allowed']} "
          f"local_up={state['local_up']}")
    t0 = time.time()
    out = R.chat(prompt, route="auto", max_tokens=32)
    dt = time.time() - t0
    print(f"provider={out.get('provider')} routed_via={out.get('routed_via')} "
          f"model={out.get('model')}")
    print(f"content={(out.get('content') or '')[:80]!r}")
    print(f"elapsed={dt:.2f}s")
    ok = out.get("provider") in (state["local_up"] or [])
    print("LOCAL_ROUTE:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
