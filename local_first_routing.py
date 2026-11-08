"""local_first_routing.py - route from what is UP: local when it can answer, paid only if allowed.

Operator rule (2026-11-01): "as you get online switch all to local so you can
slowly stop using token and let system come online autonomous".

State before: `policy.order` was lmstudio, nvidia, deepseek, xpl,
llamacpp-local - so `route="auto"` escalated to paid providers whenever LM
Studio hiccuped, and the only spend-free path was the explicit `route="local"`,
which nothing on the live paths used by default.

State after:

  * `policy.mode` + `policy.local_switch_when_up` + `policy.paid_fallback`
    govern the chain;
  * `abrasax.autonomy` writes LOGS/llm-mode.json from the supervisor's own
    liveness probe (no extra probing), and the router reads it if fresh;
  * any local provider up  -> mode local_only  -> paid providers are not in the
    chain at all (zero spend, proven by the tests);
  * no local provider      -> mode local_first -> paid allowed only when
    `paid_fallback` is true;
  * `ABRASAX_LLM_MODE` overrides everything for a one-off run;
  * the JEV gate now fires on the transition into a PAID provider, not on
    "not the first name in the list".

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
ROUTER = ROOT / "agents" / "agents_hub" / "llm_router.py"
CFG = ROOT / "CONFIG" / "llm" / "providers.json"

OLD_CHAIN = '''    cfg = _config()
    order = cfg["policy"]["order"]
    if route == "local":
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
        chain = order if route == "auto" else [route]
    errors: list[str] = []
'''

NEW_CHAIN = '''    cfg = _config()
    policy = cfg["policy"]
    order = policy["order"]
    # Local = flagged local:true in providers.json. Never inferred from the name.
    local_order = [n for n in (policy.get("zero_cost_order") or order)
                   if cfg["providers"].get(n, {}).get("local")]
    local_order += [n for n in order
                    if n not in local_order
                    and cfg["providers"].get(n, {}).get("local")]
    paid_order = [n for n in order if n not in local_order]

    mode, mode_source = "auto", "route"
    if route == "local":
        # Zero-cost chain: only providers explicitly flagged local:true. A paid
        # provider must never be reachable from here, so assert rather than trust
        # the config file.
        chain = list(local_order)
        paid = {"nvidia", "xpl"} & set(chain)
        if paid:
            raise RuntimeError(f"zero-cost route would reach paid providers: {sorted(paid)}")
        if not chain:
            raise RuntimeError("zero-cost route has no local provider configured")
    elif route in ("auto", "local_first", "local_only"):
        mode = route if route != "auto" else _autonomy_mode(cfg)[0]
        mode_source = "route" if route != "auto" else _autonomy_mode(cfg)[1]
        if mode == "local_only":
            # Prove it from the data, not from the mode string: a provider is in
            # this chain only if the config says local.
            chain = [n for n in local_order if cfg["providers"][n].get("local")]
            if not chain:
                raise RuntimeError("local_only mode but no local provider is configured")
        elif mode == "local_first":
            chain = list(local_order)
            if paid_allowed:
                chain += paid_order
        else:
            chain = list(order)
    else:
        chain = [route]
    errors: list[str] = []
'''

OLD_HINT = '''    raise RuntimeError("all providers failed: " + " | ".join(errors) if errors
                       else "no providers configured")'''

NEW_HINT = '''    if mode == "local_only":
        errors.append("mode=local_only: paid providers were never tried "
                      f"(source={mode_source}); set ABRASAX_LLM_MODE=local_first "
                      "to allow spend")
    raise RuntimeError("all providers failed: " + " | ".join(errors) if errors
                       else "no providers configured")'''

OLD_GATE = '''        if jev_gate and cfg["policy"].get("jev_gate") and route == "auto":
            if name != order[0] and not _jev_approve(
                    name, f"Primary '{order[0]}' unavailable. Errors: {errors[-1:]}"):'''
NEW_GATE = '''        if jev_gate and cfg["policy"].get("jev_gate") and route == "auto" \\
                and not prov.get("local"):
            # The gate exists to stop SPEND. Escalating between two local
            # providers costs nothing, and asking JEV there only added a
            # failure mode to the zero-cost path.
            if not _jev_approve(
                    name, f"local providers unavailable. Errors: {errors[-1:]} "):'''

HELPER_ANCHOR = '''def chat(messages: Any, route: str = "auto", model: str | None = None,'''
HELPER = '''def _autonomy_mode(cfg: dict) -> tuple[str, str]:
    """(mode, source): env override, then the supervisor's fresh state file, then policy."""
    try:
        from abrasax import autonomy
        return autonomy.effective_mode(cfg)
    except Exception:  # noqa: BLE001 - routing must survive a broken state file
        policy = cfg.get("policy") or {}
        mode = str(policy.get("mode") or "local_first")
        return (mode if mode in ("local_first", "local_only") else "local_first"), "policy"


'''

PAID_DECL = '''    errors: list[str] = []
'''
PAID_DECL_NEW = '''    errors: list[str] = []
    paid_allowed = bool(policy.get("paid_fallback", False)) and mode != "local_only"
'''


def patch_text(src: str, pairs) -> str:
    for old, new in pairs:
        if new in src:
            continue
        if src.count(old) != 1:
            raise SystemExit(f"anchor {src.count(old)}x: {old[:70]!r}")
        src = src.replace(old, new, 1)
    return src


def main() -> int:
    src = ROUTER.read_text(encoding="utf-8")
    before = src
    src = patch_text(src, [(OLD_CHAIN, NEW_CHAIN), (OLD_HINT, NEW_HINT),
                           (OLD_GATE, NEW_GATE)])
    if "_autonomy_mode(cfg)" in src and "def _autonomy_mode" not in src:
        if src.count(HELPER_ANCHOR) != 1:
            raise SystemExit("helper anchor not unique")
        src = src.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    if "paid_allowed = bool(policy" not in src:
        # first occurrence of `errors: list[str] = []` belongs to chat()
        if src.count(PAID_DECL) < 1:
            raise SystemExit("errors declaration not found")
        src = src.replace(PAID_DECL, PAID_DECL_NEW, 1)
    if src != before:
        ROUTER.write_text(src, encoding="utf-8", newline="")
        print("patched", ROUTER)
    else:
        print("router already applied")

    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    pol = cfg["policy"]
    changed = False
    if pol.get("mode") != "local_first":
        pol["mode"] = "local_first"
        changed = True
    if not pol.get("local_switch_when_up", False):
        pol["local_switch_when_up"] = True
        changed = True
    if "paid_fallback" not in pol:
        pol["paid_fallback"] = True
        changed = True
    want_order = ["lmstudio", "llamacpp-local", "nvidia", "deepseek", "xpl"]
    if pol.get("order") != want_order:
        pol["order"] = want_order
        changed = True
    if pol.get("zero_cost_order") != ["lmstudio", "llamacpp-local"]:
        pol["zero_cost_order"] = ["lmstudio", "llamacpp-local"]
        changed = True
    pol["notes"] = (
        "LOCAL-FIRST (2026-11-01). order lists local providers first; mode + "
        "local_switch_when_up + paid_fallback decide the chain. While any local "
        "provider answers, abrasax.autonomy writes mode=local_only and paid "
        "providers are never contacted (zero tokens). With no local provider, "
        "mode=local_first allows paid only because paid_fallback=true. "
        "ABRASAX_LLM_MODE=auto|local_first|local_only overrides per process. "
        "zero_cost_order is the local preference: gemma-4-e2b (quality) before "
        "the 1.2B llama.cpp. neo is never in the chain (explicit model only)."
    )
    if changed:
        CFG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8", newline="")
        print("patched", CFG)
    else:
        print("providers.json already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
