#!/usr/bin/env python3
"""fix_secret_scan_fixtures.py -- the scanner must not indict its own fixtures.

`check_repo_secrets.py` keeps a small EXCLUDED set for files that contain credential-shaped
strings *by design*; it listed only `check_secret_rules.py`. `tests/test_repo_secret_scan.py`
parametrises two real-looking tokens (that is the point of the test: the classifier must
catch them), so `scanner.main()` reported "new findings: 2" against the tree and
`test_the_real_tree_has_no_new_findings` failed -- the scanner was flagging the test that
proves the scanner works.

Also rewrites LOGS/_last_failed.txt, which is 24 NUL bytes: exactly the zero-fill crash
signature `tests/test_no_zero_filled_state.py` exists to catch (nothing writes that name any
more; the file is debris from the 2026-11-01 15:19 event).

Run: python SCRIPTS/fix_secret_scan_fixtures.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNER = ROOT / "SCRIPTS" / "automation" / "check_repo_secrets.py"
MARKER = ROOT / "LOGS" / "_last_failed.txt"

OLD = """EXCLUDED = {
    "SCRIPTS/automation/check_secret_rules.py",
}"""

NEW = """EXCLUDED = {
    "SCRIPTS/automation/check_secret_rules.py",
    # This test's whole job is to prove the classifier catches credential-shaped strings,
    # so it carries two of them as parameters. Scanning it indicts the proof, not the tree.
    "tests/test_repo_secret_scan.py",
}"""


def main() -> int:
    text = SCANNER.read_text(encoding="utf-8-sig")
    excluded = "tests/test_repo_secret_scan.py" in text
    marker_ok = MARKER.exists() and not MARKER.read_bytes()[:4096].count(0) == MARKER.stat().st_size

    if "--check" in sys.argv:
        print(("PASS " if excluded and marker_ok else "FAIL ")
              + f"scanner_excludes_own_fixtures={excluded} last_failed_not_zero_filled={marker_ok}")
        return 0 if excluded and marker_ok else 1

    if not excluded:
        if OLD not in text:
            print("FAIL  EXCLUDED block not found")
            return 1
        bak = SCANNER.with_suffix(".py.bak-fixtures")
        if not bak.exists():
            bak.write_text(text, encoding="utf-8")
        SCANNER.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
        print("  + EXCLUDED tests/test_repo_secret_scan.py")

    if not marker_ok and MARKER.exists():
        MARKER.write_text(
            "none\n"
            "# rewritten 2026-11-02: this file held 24 NUL bytes (the zero-fill crash\n"
            "# signature tests/test_no_zero_filled_state.py exists to catch). Nothing in\n"
            "# the tree writes this name any more.\n",
            encoding="utf-8",
        )
        print("  + LOGS/_last_failed.txt rewritten (was zero-filled)")

    print("secret-scan fixtures excluded; zero-fill debris cleared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
