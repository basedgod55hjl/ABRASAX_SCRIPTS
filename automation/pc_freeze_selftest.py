"""Prove the freeze recorder's incident detector works, without touching the
live heartbeat.

The detector is the only part of the recorder whose correctness cannot be
observed until the next hang, so it is tested now: inject a heartbeat stamped
half an hour before this boot and require that classify() cites something from
the real event log. A detector that reports "freeze" with no evidence is the
same class of bug as a gate that passes because it checked nothing.

The synthetic incident is removed from the ledger afterwards -- incidents.jsonl
must only ever contain things that actually happened.

    python SCRIPTS/automation/pc_freeze_selftest.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pc_freeze_recorder as rec  # noqa: E402


def drop_synthetic() -> None:
    try:
        with open(rec.INCIDENTS, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
    except OSError:
        return
    kept = [ln for ln in lines if '"last_marker": "selftest"' not in ln]
    if len(kept) != len(lines):
        with open(rec.INCIDENTS, "w", encoding="utf-8") as fh:
            fh.writelines(kept)
        print("removed %d synthetic incident line(s)" % (len(lines) - len(kept)))


def main() -> int:
    boot = rec.boot_time()
    if not boot:
        print("FAIL no boot time")
        return 1
    synthetic = {"ts": boot - 1800, "iso": "synthetic", "gpu": {},
                 "sys": {}, "python": [], "last_marker": "selftest"}
    try:
        inc = rec.check_previous_run(synthetic)
        if not inc:
            print("FAIL detector returned nothing for a pre-boot heartbeat")
            return 1
        shut = inc.get("previous_shutdown") or {}
        print("kind=%s dark=%.0fs classified=%s"
              % (inc["kind"], inc["dead_seconds_before_boot"],
                 shut.get("classified")))
        bug = (shut.get("bugcheck") or "").splitlines()
        unexpected = (shut.get("unexpected") or "").splitlines()
        clean = (shut.get("clean_initiated") or "").splitlines()
        for label, lines in (("bugcheck", bug), ("unexpected", unexpected),
                             ("clean_initiated", clean)):
            if lines:
                print("%s=%s" % (label, lines[0][:110]))
        ok = (inc["kind"] == "freeze"
              and bool(shut.get("bugcheck") or shut.get("unexpected")))
        print("RESULT: %s" % ("PASS detector fires and cites the event log"
                             if ok else "FAIL detector fired without evidence"))
        return 0 if ok else 1
    finally:
        drop_synthetic()


if __name__ == "__main__":
    sys.exit(main())
