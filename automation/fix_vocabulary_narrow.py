"""Narrow the vocabulary: CLOSED and MISSING are not port statuses here.

Measured, both false positives introduced by the previous widening:

  DOC/RUNBOOK.md:79
      curl ... http://127.0.0.1:1234/v1/models   # 401 = token missing on caller
      "MISSING" is inside a shell COMMENT explaining an HTTP code. The port is up.

  DOC/GAP-BOARD.md:77
      ... anything else fails closed with SystemExit unless ...
      "CLOSED" is part of "fails closed", a security property. The port is up.

In technical prose these words carry other meanings, so including them made the
verifier noisier, not better. The honest position:

  UP set keeps OPEN/LIVE/ALIVE/LISTENING/ONLINE/HEALTHY/RUNNING -- unambiguous
  DOWN set keeps DOWN/OFFLINE/STOPPED/DEAD and drops CLOSED + MISSING + ABSENT,
  which are ambiguous in this corpus

Also: a status word inside a '#' shell comment is not a status claim, so comments
are stripped before matching.

Twenty-first and twenty-second false reds of the night, both from widening a
pattern instead of proving it.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "COMMENT_RE" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD_DOWN = ('DOWN_WORDS = r"(?:NOT\\s+LISTENING|OFFLINE|CLOSED|STOPPED|DOWN|'
            'DEAD|ABSENT|MISSING)"')
NEW_DOWN = ('# CLOSED / MISSING / ABSENT removed: in this corpus they appear as\n'
            '# "fails closed" (security) and "# 401 = token missing" (comment).\n'
            'DOWN_WORDS = r"(?:NOT\\s+LISTENING|OFFLINE|STOPPED|DOWN|DEAD)"')
if OLD_DOWN not in src:
    print("ANCHOR-NOT-FOUND: DOWN_WORDS")
    sys.exit(1)
src = src.replace(OLD_DOWN, NEW_DOWN, 1)

# strip shell comments before scanning
OLD_SCAN = '''    seen = set()
    for rx in (ROW, ROW2):'''
NEW_SCAN = '''    # A status word after '#' is a shell comment, not a claim. RUNBOOK.md has
    # "curl ... :1234/v1/models   # 401 = token missing on caller", which cost a
    # false positive.
    COMMENT_RE = re.compile(r"#[^\\n]*")
    text = COMMENT_RE.sub("", text)

    seen = set()
    for rx in (ROW, ROW2):'''
if OLD_SCAN not in src:
    print("ANCHOR-NOT-FOUND: scan loop")
    sys.exit(1)
src = src.replace(OLD_SCAN, NEW_SCAN, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: ambiguous words dropped; shell comments stripped before matching")
