"""Correct the doc claims the live verifier proved wrong -- starting with my own.

verify_docs_live.py found 19 stale claims. They sort into three kinds, and each
needs a different response:

A  MY OWN DOC IS WRONG
     :9700  doc says OFFLINE  live is OPEN   DOC/IMGUI-OVERLAY.md
   I wrote that section describing the failure mode; placed where it reads as a
   current status, it is simply false now. Fix the wording so the failure state is
   labelled as hypothetical.

B  DOCS THAT PREDATE A RENAME / RETIREMENT (:9000)
     ARCHITECTURE.md, DOC-GRAPH.md, FINAL_RUN_STATE.md, INDEX.md,
     REPORTS/DOC-INDEX.md, REPORTS/E2E-LIVE.md
   Six documents still describe :9000 as the live gateway. SERVICES-PROD.md already
   established that :9000 never had a listener and the live gateway is :9001. These
   get a dated correction banner rather than a silent edit, because the surrounding
   prose explains a design that changed.

C  DOCS CLAIMING A SERVICE IS DOWN WHEN IT IS UP (:9624 :9625 :9626 :9782 :9050)
   Those are notes taken during an outage, still readable as current status.

This script appends a single dated CORRECTION block to each affected document,
listing exactly what the live check found. It does not rewrite prose, does not
delete, and is idempotent.

dry-run by default; --apply writes .bak- copies first.
"""
import os
import sys
import time

ROOT = r"C:\ABRASAX"
APPLY = "--apply" in sys.argv
STAMP = time.strftime("%Y-%m-%d")

# doc -> (line describing what is wrong)
CORRECTIONS = {
    "DOC/IMGUI-OVERLAY.md": [
        ":9700 is described as OFFLINE in the limits section. That paragraph "
        "describes a failure mode, not the current state -- the renderer has been "
        "live throughout and `verify_docs_live.py` reads OPEN.",
    ],
    "DOC/ARCHITECTURE.md": [
        ":9000 is presented as the gateway. The live gateway is :9001 "
        "(`abrasax/gateway.py`). :9000 has no listener; DOC/SERVICES-PROD.md "
        "records that it never did, and the entry was renamed `vlc-7d-sampler` :8778.",
    ],
    "DOC/DOC-GRAPH.md": [
        ":9000 and :9782 are carried as live nodes. Live check: :9000 CLOSED, "
        ":9782 OPEN.",
    ],
    "DOC/FINAL_RUN_STATE.md": [
        ":9000 is listed as ONLINE. Live check: CLOSED. A measured-state block was "
        "prepended on 2026-10-18; this note records that the underlying table is "
        "history, not current state.",
    ],
    "DOC/INDEX.md": [
        ":9000 is described as HEALTHY. Live check: CLOSED. The live gateway is "
        ":9001.",
    ],
    "DOC/REPORTS/DOC-INDEX.md": [
        ":9000 is described as ONLINE. Live check: CLOSED.",
    ],
    "DOC/REPORTS/E2E-LIVE.md": [
        ":9000 is described as LIVE. Live check: CLOSED.",
    ],
    "DOC/BRAIN.md": [
        ":9623 is described as RUNNING and :9624/:9625 as DOWN. Live check: "
        ":9623 CLOSED, :9624 OPEN, :9625 OPEN -- the reverse.",
    ],
    "DOC/DISK-INVENTORY.md": [
        ":9626 is described as DOWN. Live check: OPEN.",
    ],
    "DOC/OPS-MASTER-PLAN.md": [
        ":9782 is described as DOWN. Live check: OPEN.",
    ],
    "DOC/inventory/SERVICES_INVENTORY.md": [
        ":9050 is described as DOWN. Live check: OPEN.",
    ],
    "DOC/SERVICE-CLEAN.md": [
        ":21416 is described as UP. Live check: CLOSED.",
    ],
    "DOC/REPORTS/M6-UI.md": [
        ":8090 is described as DEAD and :9099 as RUNNING. Live check: :8090 OPEN, "
        ":9099 CLOSED.",
    ],
    "DOC/REPORTS/SERVICES-PROD.md": [
        ":8877 is described as LISTENING. Live check: CLOSED.",
    ],
    "DOC/DISK-CLEAN/VERIFY.md": [
        ":9623 is described as UP. Live check: CLOSED.",
    ],
}

MARKER = "<!-- LIVE-VERIFY"


def main() -> int:
    changed = 0
    missing = 0

    for rel, lines in sorted(CORRECTIONS.items()):
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(full):
            print(f"MISSING {rel}")
            missing += 1
            continue

        text = open(full, encoding="utf-8", errors="ignore").read()
        if MARKER in text:
            print(f"already corrected: {rel}")
            continue

        block = [
            "",
            f"<!-- LIVE-VERIFY {STAMP} -->",
            f"> **LIVE CORRECTION ({STAMP})** — verified against the running system by",
            "> `SCRIPTS/automation/verify_docs_live.py`.",
            ">",
        ]
        for ln in lines:
            block.append(f"> - {ln}")
        block.append("")
        block.append(f"<!-- /LIVE-VERIFY {STAMP} -->")
        block.append("")

        new = text.rstrip("\n") + "\n" + "\n".join(block)

        print(f"{'correcting' if APPLY else 'would correct'}: {rel}")
        if APPLY:
            import shutil
            backup = full + ".bak-" + time.strftime("%Y%m%d-%H%M")
            shutil.copy2(full, backup)
            open(full, "w", encoding="utf-8", newline="").write(new)
            changed += 1

    print(f"\n{len(CORRECTIONS)} doc(s) targeted, {changed} corrected, {missing} missing")
    if not APPLY:
        print("dry run -- re-run with --apply")
        return 0
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
