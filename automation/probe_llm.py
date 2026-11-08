"""Probe the live LLM router so the brain field can be driven by real inference.

Goal: prove we can get a short text reply from the configured provider chain
(lmstudio -> nvidia -> xpl) with a measurable latency. If this works, the
renderer can be fed real AI output instead of synthetic activation.
"""
import json
import os
import sys
import time

sys.path.insert(0, r"C:\ABRASAX")

from abrasax import llm

print("llm module:", llm.__file__)
print("probe():")
try:
    for row in llm.probe() or []:
        print("  ", row)
except Exception as e:  # noqa: BLE001
    print("  probe failed:", type(e).__name__, e)

print("\nask():")
t0 = time.time()
try:
    r = llm.ask("Reply with exactly: STRING-BRAIN-OK", max_tokens=24)
    dt = time.time() - t0
    print(f"  elapsed {dt:.2f}s")
    print(f"  type    {type(r).__name__}")
    if isinstance(r, dict):
        for k in ("text", "content", "reply", "route", "routed_via", "provider",
                  "tokens", "usage", "model"):
            if k in r:
                print(f"  {k:10s}= {str(r[k])[:160]}")
        print("  keys    =", sorted(r.keys()))
    else:
        print("  repr    =", repr(r)[:400])
except Exception as e:  # noqa: BLE001
    print("  FAILED:", type(e).__name__, e)
sys.exit(0)
