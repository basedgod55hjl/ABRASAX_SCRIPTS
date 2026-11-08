"""Verify the CONFIG directory's live contract.

Questions this answers with measurements, not assumptions:
  1. Do the config files that real code reads actually exist and parse?
  2. Does agents_hub.config_gateways degrade safely when config/gateways.json
     is absent (it is absent -- grep says so)?
  3. Is CONFIG/llm/providers.json consistent with the LM Studio server that is
     actually listening right now?
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
CFG = ROOT / "CONFIG"
sys.path.insert(0, str(ROOT))

print("--- 1. config files referenced by live code")
checks = {
    "CONFIG/hardware/profile.json": CFG / "hardware/profile.json",
    "CONFIG/llm/providers.json": CFG / "llm/providers.json",
    "CONFIG/llm/live-models.json": CFG / "llm/live-models.json",
    "CONFIG/mcp.abrasax.json": CFG / "mcp.abrasax.json",
    "CONFIG/unity-7000.0.0a10-windows.json": CFG / "unity-7000.0.0a10-windows.json",
    "config/gateways.json": ROOT / "config" / "gateways.json",
}
for label, p in checks.items():
    if not p.exists():
        print(f"  MISSING  {label}")
        continue
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        n = len(data) if isinstance(data, (dict, list)) else "-"
        print(f"  ok       {label}  ({p.stat().st_size} B, {n} top-level keys)")
    except Exception as exc:  # noqa: BLE001
        print(f"  BADJSON  {label}  {type(exc).__name__}: {exc}")

print("\n--- 2. gateway path resolution degrades safely")
try:
    from AGENTS.agents_hub.config_gateways import apply_gateway_paths_to_environ
    applied = apply_gateway_paths_to_environ(ROOT)
    print(f"  imports OK; applied={applied!r} (empty dict = no gateways.json, safe)")
except Exception as exc:  # noqa: BLE001
    print(f"  IMPORT/RUNTIME FAILURE: {type(exc).__name__}: {exc}")
    raise SystemExit(1)

print("\n--- 3. providers.json vs the live LM Studio server")
prov = json.loads((CFG / "llm/providers.json").read_text(encoding="utf-8"))
lm = prov["providers"]["lmstudio"]
base = lm["base_url"]
print(f"  configured base_url: {base}")
try:
    with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=8) as r:
        live = {m["id"] for m in json.loads(r.read().decode())["data"]}
    print(f"  live server: UP, {len(live)} models")
except Exception as exc:  # noqa: BLE001
    print(f"  live server: DOWN ({type(exc).__name__}) -- cannot cross-check")
    live = set()

if live:
    named = {k: v for k, v in lm["models"].items() if isinstance(v, str)}
    missing = {k: v for k, v in named.items() if v not in live}
    if missing:
        print(f"  {len(missing)} alias(es) point at models the server does not list:")
        for k, v in missing.items():
            print(f"    {k:18} -> {v}")
    else:
        print(f"  all {len(named)} model aliases resolve to live models")
    extra = live - set(named.values())
    print(f"  server also lists {len(extra)} model(s) with no alias")

print("\n--- 4. policy sanity")
pol = prov.get("policy", {})
order = pol.get("order", [])
print(f"  order={order} auto_fallback={pol.get('auto_fallback')} jev_gate={pol.get('jev_gate')}")
unknown = [o for o in order if o not in prov["providers"]]
print(f"  order entries with no provider block: {unknown or 'none'}")
