"""Final tightening: a line number is not a port, even in a table cell.

Remaining false positives after the last fix:

    :102  doc says LIVE  DOC/AGENTS-WIRE.md
    :112  doc says UP    DOC/SERVICES-PROD.md
    :122  doc says LIVE  DOC/ARCHITECTURE.md
    :334  doc says UP    DOC/SERVICES-PROD.md

These come from the table shape: the docs contain rows like
    | :102 | something | LIVE |
where 102 is a line number the author cited. The colon makes it look like a port.

Two facts disambiguate:
  * a real service port in this project is 4 digits (9000, 9001, 9626, 9777) or a
    well-known 3-digit one (80, 443) -- NOT a bare 3-digit number in the 100-999
    range, which is overwhelmingly a line reference
  * line numbers cluster in ranges like 60-700 with no service meaning

So: require 4-5 digit ports. Three-digit ports are rejected unless they are in the
IANA well-known set (80, 443, 8080 is 4-digit anyway). This will miss a genuine
":443" claim, which the output states rather than hides.

The list that survives is the one worth acting on, and it is already showing real
findings:
    :9000  six docs claim ONLINE/HEALTHY  -> CLOSED
    :9624 :9625 :9626 :9782 :9700  docs claim DOWN  -> OPEN
    :9623  docs claim UP                  -> CLOSED
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "WELL_KNOWN" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''            port = int(raw)
            if not (1 <= port <= 65535):
                continue'''

NEW = '''            port = int(raw)
            if not (1 <= port <= 65535):
                continue
            # A 3-digit number near a status word is almost always a line
            # reference, not a port. Measured: 102, 112, 122, 124, 140, 191, 204,
            # 215, 224, 230, 234 were all line numbers. Only accept 4-5 digit
            # ports, or a 3-digit one that is genuinely well-known.
            WELL_KNOWN = {80, 443, 110, 143, 993, 995, 587, 465, 2525}
            if port < 1000 and port not in WELL_KNOWN:
                continue'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: port range check")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)

# state the limitation in the output rather than hiding it
OLD_NOTE = '''print("  test counts ('378 passed'), prose status words without a port, and")
print("  'as of <date>' snapshots are NOT machine-checked by this tool.")'''
NEW_NOTE = '''print("  test counts ('378 passed'), prose status words without a port, and")
print("  'as of <date>' snapshots are NOT machine-checked by this tool.")
print("  Three-digit port claims are ignored (they are line numbers far more often")
print("  than ports); only 4-5 digit ports and IANA well-known ports are checked.")'''
if OLD_NOTE in src:
    src = src.replace(OLD_NOTE, NEW_NOTE, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: only 4-5 digit ports (plus IANA well-known) count as claims")
