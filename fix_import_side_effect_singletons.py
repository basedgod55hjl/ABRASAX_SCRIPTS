"""fix_import_side_effect_singletons.py -- claim role locks in main(), never on import.

Measured 2026-11-01 16:26Z: the full suite died during *collection* with

    tests/test_jev_markers.py:23: import orchestrator as orch
    orchestrator.py:55: raise SystemExit(0)
    INTERNALERROR> mainloop: caught unexpected SystemExit!

`orchestrator.py` and `host.py` both claimed their singleton lock at MODULE
SCOPE and raised SystemExit(0) when the claim lost. Consequences:

  * `import orchestrator` (tests/test_jev_gate.py, tests/test_jev_markers.py,
    any external tool) silently killed the importer when a real orchestrator
    was running -- and in pytest that is an INTERNALERROR, not a test failure.
  * even when the claim won, the import SQUATTED the live role lock for the
    whole process lifetime: while pytest ran, the real orchestrator could not
    start and would exit 0 with only a printed line to show for it.

Fix: a `_claim_singleton(role)` helper, called from the top of main(). Importing
either module is now side-effect free; running either binary is still singleton.

Idempotent. Backs up to <file>.bak-importside-YYYYMMDD.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")

HELPER = '''def _claim_singleton(role: str) -> bool:
    """Claim the role lock. Called from main(), NEVER at import time.

    A module-scope claim meant `import orchestrator` / `import host` (tests,
    external tools) took the live role lock, and raised SystemExit(0) -- an
    instant process kill -- when another instance already held it. Measured
    2026-11-01: pytest collection died in tests/test_jev_markers.py with
    "SystemExit: 0" from orchestrator.py:55.
    """
    import sys as _s

    _s.path.insert(0, r"C:\\abrasax\\SCRIPTS\\automation")
    from abrasax_singleton import claim as _claim

    return bool(_claim(role))


'''

OLD_TEMPLATE = '''import sys as _sys
_sys.path.insert(0, r"C:\\abrasax\\SCRIPTS\\automation")
from abrasax_singleton import claim as _claim

if not _claim("{role}"):
    print("ABRASAX: {role} already running (singleton guard) -- exiting", flush=True)
    raise SystemExit(0)
'''

MAIN_ANCHORS = {
    "orchestrator.py": ("def main():\n    load_env()\n",
                        "def main():\n"
                        '    if not _claim_singleton("orchestrator"):\n'
                        '        print("ABRASAX: orchestrator already running '
                        '(singleton guard) -- exiting", flush=True)\n'
                        "        return 0\n"
                        "    load_env()\n"),
    "host.py": ("def main():\n    os.makedirs(os.path.dirname(LOG), exist_ok=True)\n",
                "def main():\n"
                '    if not _claim_singleton("host"):\n'
                '        print("ABRASAX: host already running (singleton guard) '
                '-- exiting", flush=True)\n'
                "        return 0\n"
                "    os.makedirs(os.path.dirname(LOG), exist_ok=True)\n"),
}


def patch(name: str, role: str) -> bool:
    path = ROOT / name
    src = path.read_text(encoding="utf-8")
    if "_claim_singleton" in src:
        print(f"{name}: already patched")
        return True
    old = OLD_TEMPLATE.format(role=role)
    anchor, new_anchor = MAIN_ANCHORS[name]
    for needle in (old, anchor):
        if needle not in src:
            print(f"{name}: ANCHOR NOT FOUND ({needle.splitlines()[0]!r}) -- refusing to guess")
            return False
    bak = path.with_suffix(".py.bak-importside-" + dt.date.today().strftime("%Y%m%d"))
    bak.write_text(src, encoding="utf-8")
    out = src.replace(old, HELPER, 1).replace(anchor, new_anchor, 1)
    path.write_text(out, encoding="utf-8")
    print(f"{name}: patched (backup {bak.name})")
    return True


def main() -> int:
    ok = patch("orchestrator.py", "orchestrator")
    ok = patch("host.py", "host") and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
