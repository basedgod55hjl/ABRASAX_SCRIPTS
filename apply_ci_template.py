"""apply_ci_template.py — replace the toothless workflow in every source tree.

The old ci.yml could not fail: `ruff check . || true` always exits 0, and the
compile loop ended each iteration with `echo "FAIL"` instead of exiting non-zero.
A gate that cannot fail is worse than none, because it produces a green tick that
people rely on.

This copies DOC/templates/ci.yml over every .github/workflows/ci.yml under the
repo roots that feed build_now, keeping a .bak next to each replaced file.

    python SCRIPTS/apply_ci_template.py --check
    python SCRIPTS/apply_ci_template.py --go
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "DOC" / "templates" / "ci.yml"

# every source tree that publishes via tools/abx/repos24
SOURCES = [
    ROOT / "UI" / "abrasax-ui",
    ROOT / "SYSTEMS" / "ABRASAX-7D-Crystal",
    ROOT / "SYSTEMS" / "ABRASAX-System32-AI",
    ROOT / "AGENTS" / "DEVOPS" / "ABRASAX-DevOps",
    ROOT / "AGENTS" / "SYSTEM32" / "ABRASAX-System32-AI",
    ROOT / "AGENTS" / "TS-SWARM" / "ABRASAX-Agents",
    ROOT / "AGENTS" / "ARCHIVE" / "ui-shell" / "ABRASAX-UI",
    ROOT / "AGENTS" / "ARCHIVE" / "_from-source" / "ABRASAX-SWARM-AI_from-source",
]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    go = "--go" in argv
    new = TEMPLATE.read_text(encoding="utf-8")
    new_hash = hashlib.sha256(new.encode()).hexdigest()[:12]
    print(f"template {TEMPLATE.name} sha256:{new_hash} ({len(new)} chars)\n")

    changed = 0
    for src in SOURCES:
        wf = src / ".github" / "workflows" / "ci.yml"
        if not wf.exists():
            print(f"  SKIP   {wf} (absent)")
            continue
        old = wf.read_text(encoding="utf-8", errors="replace")
        same = old.strip() == new.strip()
        print(f"  {'SAME  ' if same else 'PATCH '} {wf}")
        if same or not go:
            continue
        shutil.copy2(wf, wf.with_suffix(".yml.bak-ci"))
        wf.write_text(new, encoding="utf-8")
        changed += 1

    print(f"\n{'patched ' + str(changed) if go else 'dry run'} "
          f"(pass --go to write; .bak-ci kept next to each)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
