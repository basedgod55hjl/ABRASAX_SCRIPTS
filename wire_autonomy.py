"""wire_autonomy.py - make the local-first decision visible and automatic.

Two wirings, both small:

1. `python -m abrasax autonomy` is a CLI verb (parser + dispatch). The module
   existed but the CLI did not know it, so the only way to see the decision was
   to remember a module path.

2. The supervisor writes LOGS/llm-mode.json every tick from the liveness it
   already computed. No extra probing, no second opinion: the process that
   knows what is UP is the process that decides what the router may use. The
   router reads that file only while it is fresh (180 s), so a dead supervisor
   degrades routing to the config policy instead of pinning it.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
CLI = ROOT / "abrasax" / "cli.py"
SUP = ROOT / "SCRIPTS" / "automation" / "supervisor.py"

CLI_PARSER_ANCHOR = '''    p_svc = sub.add_parser("services", help="service catalog + live health")'''
CLI_PARSER_NEW = '''    sub.add_parser("autonomy", help="local-first LLM routing state (mode/paid)")

    p_svc = sub.add_parser("services", help="service catalog + live health")'''

CLI_DISPATCH_ANCHOR = '''    elif args.command == "services":'''
CLI_DISPATCH_NEW = '''    elif args.command == "autonomy":
        from . import autonomy
        return autonomy.main([])
    elif args.command == "services":'''

SUP_ANCHOR = '''    chk = integrity()
    if not chk["ok"]:
        _ledger({"event": "missing", **chk})'''
SUP_NEW = '''    # Local-first routing: the router may only prefer local providers while it
    # knows they are up, and this tick is that knowledge. Written after the
    # summary so a crash cannot leave a half-formed decision behind.
    try:
        from abrasax import autonomy
        _llm_mode = autonomy.snapshot(up_ids=up_ids, write_state=True)
    except Exception as exc:  # noqa: BLE001 - routing policy must not kill a tick
        _llm_mode = {"error": repr(exc)}
        _ledger({"event": "autonomy_error", "error": repr(exc)})

    chk = integrity()
    if not chk["ok"]:
        _ledger({"event": "missing", **chk})'''

SUP_STATE_OLD = '''        "started": started, "integrity_ok": chk["ok"],'''
SUP_STATE_NEW = '''        "started": started, "integrity_ok": chk["ok"],
        "llm_mode": (_llm_mode or {}).get("mode"),'''


def patch(path: Path, pairs) -> bool:
    src = path.read_text(encoding="utf-8")
    before = src
    for old, new in pairs:
        if new in src:
            continue
        if src.count(old) != 1:
            raise SystemExit(f"{path}: anchor {src.count(old)}x: {old[:60]!r}")
        src = src.replace(old, new, 1)
    if src != before:
        path.write_text(src, encoding="utf-8", newline="")
        return True
    return False


def main() -> int:
    changed = []
    if patch(CLI, [(CLI_PARSER_ANCHOR, CLI_PARSER_NEW),
                   (CLI_DISPATCH_ANCHOR, CLI_DISPATCH_NEW)]):
        changed.append(CLI)
    if patch(SUP, [(SUP_ANCHOR, SUP_NEW), (SUP_STATE_OLD, SUP_STATE_NEW)]):
        changed.append(SUP)
    for p in changed:
        print("patched", p)
    if not changed:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
