"""fix_ops_absent_is_not_down.py - an install that is not on this host is not an incident.

MEASURED 2026-11-01T17:23:59Z, healthy stack, 16/16 non-optional services up:

    "signature": "down:comfyui|down:imagegen",
    "critical_down": ["comfyui", "imagegen"]

Both are Stability-Matrix rows whose entry path names a user that does not exist
on this box (``C:\\Users\\sirch\\...``; this host is ``lucar``). The catalog
already marks them ``optional: true``; ops_monitor kept its own hardcoded
three-id OPTIONAL set instead of reading that flag. Result: the run could never
reach "healthy", so the alert stream was permanently red and worthless.

Two distinctions this adds:

* **absent** - the entry path does not exist. Restarting cannot fix it, so it is
  reported (`services_absent`, `absent:<id>`) but is not a critical-down.
* **down** - the entry exists and the service is not answering. That is an
  incident, and `critical_down` keeps exactly that meaning.

Optionality also now comes from the catalog's own flag, with the old explicit
set kept only as a floor.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\SCRIPTS\automation\ops_monitor.py")

HELPERS = '''
# ---------------------------------------------------------------------------
# "absent" is an install fact; "down" is an incident
# ---------------------------------------------------------------------------
def _entry_path(spec: dict) -> Path | None:
    entry = spec.get("entry")
    if not entry:
        return None
    p = Path(str(entry))
    return p if p.is_absolute() else ROOT / p


def classify_down(probed: list[dict], down: list[str]) -> tuple[list[str], list[str]]:
    """Split ``down`` into (absent, really-down).

    An entry path that does not exist cannot be started by any retry, so it must
    not be counted as a critical outage - that is how a permanent red signature
    trains the operator to ignore the board.
    """
    by_id = {s["id"]: s for s in probed}
    absent = [sid for sid in down
              if (p := _entry_path(by_id.get(sid) or {})) is not None
              and not p.exists()]
    return absent, [sid for sid in down if sid not in absent]


def optional_ids(probed: list[dict]) -> set[str]:
    """The catalog's own ``optional`` flag, plus rows that are never production."""
    return ({s["id"] for s in probed if s.get("optional")}
            | {"codec-gateway", "vlc-7d-sampler", "gateway"})

'''

OLD = '''    problems: list[str] = []
    # Optional services (external samplers, non-production bridges) are tracked but never
    # treated as incidents. Keep this list narrow and explicit.
    OPTIONAL = {"codec-gateway", "vlc-7d-sampler", "gateway"}
    critical_down = [s for s in down if s not in OPTIONAL]
    problems += [f"down:{s}" for s in critical_down]
'''

NEW = '''    problems: list[str] = []
    # Optional services (external samplers, non-production bridges) are tracked but never
    # treated as incidents; the flag lives in the catalog so this file cannot drift
    # from it (it already had: comfyui/imagegen are optional there and were counted
    # as critical here, pinning the signature red on a host without that install).
    absent, down_real = classify_down(probed, down)
    OPTIONAL = optional_ids(probed)
    critical_down = [s for s in down_real if s not in OPTIONAL]
    problems += [f"down:{s}" for s in critical_down]
    critical_absent = [s for s in absent if s not in OPTIONAL]
    problems += [f"absent:{s}" for s in critical_absent]
'''

OLD_STATE = '''        "services_down": down,
        "critical_down": critical_down,'''
NEW_STATE = '''        "services_down": down,
        "services_absent": absent,
        "critical_down": critical_down,
        "critical_absent": critical_absent,'''

OLD_LEDGER = '''                             ("ts", "signature", "problems", "services_down", "procs",
                              "supervisor_age_s", "buildloop_age_s", "queue_pending", "heals")}) + "\\n")'''
NEW_LEDGER = '''                             ("ts", "signature", "problems", "services_down", "services_absent",
                              "procs", "supervisor_age_s", "buildloop_age_s",
                              "queue_pending", "heals")}) + "\\n")'''

ANCHOR = '''def snapshot(dry_run: bool = False) -> dict:'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "def classify_down(" in src:
        print("already applied")
        return 0
    for old, new in ((OLD, NEW), (OLD_STATE, NEW_STATE), (OLD_LEDGER, NEW_LEDGER)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor not unique ({src.count(old)}x): {old[:70]!r}")
        src = src.replace(old, new, 1)
    if src.count(ANCHOR) != 1:
        raise SystemExit("snapshot anchor not unique")
    src = src.replace(ANCHOR, HELPERS.lstrip("\n") + ANCHOR, 1)
    TARGET.write_text(src, encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
