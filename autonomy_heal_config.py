"""autonomy_heal_config.py - the runtime heals a BOM in its own provider config.

MEASURED 2026-11-01: `CONFIG/llm/providers.json` grew a UTF-8 BOM twice in one
hour. Every reader that used plain `utf-8` then failed (the router, the gateway,
`tests/test_neo_provider_guard.py`), i.e. one external tool writing the file in
PowerShell's default encoding could take the whole routing layer offline.

Two layers now:
  * readers accept a BOM (`utf-8-sig`) - done earlier, and the test that reads
    the file is fixed here too, because a config file is input from other tools;
  * the supervisor heals the file on every tick: if it starts with a BOM, it is
    rewritten without one. A window with a broken config can then last at most
    one tick instead of until a human notices.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
AUTONOMY = ROOT / "abrasax" / "autonomy.py"
SUP = ROOT / "SCRIPTS" / "automation" / "supervisor.py"
TEST = ROOT / "tests" / "test_neo_provider_guard.py"

HEAL = '''

BOM = b"\\xef\\xbb\\xbf"


def heal_config(path: Path | None = None) -> bool:
    """Strip a UTF-8 BOM from the provider config. True if it was there.

    The BOM is not ours: nothing in this tree writes one (`json.dumps` + UTF-8
    does not), but PowerShell 5.1 `Set-Content`/`Out-File` does, and more than one
    script in SCRIPTS/automation rewrites this file. A BOM is three invisible
    bytes that made `_config()` raise for every caller, so the runtime removes it
    rather than arguing with the tool that added it.
    """
    path = Path(path or CFG)
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    if not raw.startswith(BOM):
        return False
    try:
        data = json.loads(raw[len(BOM):].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    path.write_text(json.dumps(data, indent=2) + "\\n", encoding="utf-8", newline="")
    return True
'''

SUP_OLD = '''    try:
        from abrasax import autonomy
        _llm_mode = autonomy.snapshot(up_ids=up_ids, write_state=True)'''
SUP_NEW = '''    try:
        from abrasax import autonomy
        if autonomy.heal_config():
            _ledger({"event": "config_healed", "file": "CONFIG/llm/providers.json",
                     "detail": "UTF-8 BOM stripped"})
        _llm_mode = autonomy.snapshot(up_ids=up_ids, write_state=True)'''


def main() -> int:
    src = AUTONOMY.read_text(encoding="utf-8")
    if "def heal_config" not in src:
        anchor = '''def read(max_age_s: float = FRESH_S) -> dict | None:'''
        if src.count(anchor) != 1:
            raise SystemExit("autonomy anchor not unique")
        src = src.replace(anchor, HEAL.strip("\n") + "\n\n\n" + anchor, 1)
        AUTONOMY.write_text(src, encoding="utf-8", newline="")
        print("patched", AUTONOMY)
    else:
        print("autonomy already patched")

    sup = SUP.read_text(encoding="utf-8")
    if "autonomy.heal_config()" not in sup:
        if sup.count(SUP_OLD) != 1:
            raise SystemExit("supervisor anchor not unique")
        SUP.write_text(sup.replace(SUP_OLD, SUP_NEW, 1), encoding="utf-8", newline="")
        print("patched", SUP)
    else:
        print("supervisor already patched")

    t = TEST.read_text(encoding="utf-8")
    if 'encoding="utf-8-sig"' not in t:
        t2 = t.replace('read_text(encoding="utf-8")', 'read_text(encoding="utf-8-sig")')
        TEST.write_text(t2, encoding="utf-8", newline="")
        print("patched", TEST)
    else:
        print("test already patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
