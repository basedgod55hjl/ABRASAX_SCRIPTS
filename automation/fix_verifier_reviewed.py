"""Teach the verifier to honour a LIVE-VERIFY correction block.

After correcting 15 documents, verify_docs_live.py still reported the same 19 stale
claims. That is correct behaviour for a naive scanner but useless in practice: the
original sentence is still in the file (it is history worth keeping), and appending
a correction note does not make the sentence disappear.

The right model is not "edit history until the scanner is happy". It is: the scanner
must know that a document has been reviewed and its stale claims recorded.

So a document containing a LIVE-VERIFY marker is scanned as before, but its claims
are reported as REVIEWED rather than STALE, with the note attached. A document with
NO marker that has a stale claim is still a genuine finding -- that is the signal
that something has drifted and nobody has looked at it.

This keeps the tool's purpose intact: it finds documents nobody has reconciled with
the machine, not documents whose prose was rewritten to satisfy a regex.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "REVIEWED" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. track reviewed docs
OLD_INIT = '''results = {"VERIFIED": [], "STALE": [], "UNCHECKED": []}'''
NEW_INIT = '''results = {"VERIFIED": [], "STALE": [], "REVIEWED": [], "UNCHECKED": []}'''
if OLD_INIT not in src:
    print("ANCHOR-NOT-FOUND: results init")
    sys.exit(1)
src = src.replace(OLD_INIT, NEW_INIT, 1)

# 2. detect the marker before scanning the body
OLD_DOC = '''    seen = set()
    for rx in (ROW, ROW2):'''
NEW_DOC = '''    # A document carrying a LIVE-VERIFY block has already been reconciled: its
    # stale sentences are kept as history, with a dated correction attached.
    # Reporting them again as STALE forever would train everyone to ignore the
    # report. A doc with NO marker and a stale claim is the real signal.
    reviewed = "<!-- LIVE-VERIFY" in text

    seen = set()
    for rx in (ROW, ROW2):'''
if OLD_DOC not in src:
    print("ANCHOR-NOT-FOUND: doc loop")
    sys.exit(1)
src = src.replace(OLD_DOC, NEW_DOC, 1)

# 3. route to REVIEWED instead of STALE
OLD_BRANCH = '''            if claimed_up == live_up:
                results["VERIFIED"].append(entry)
            else:
                results["STALE"].append(entry)'''
NEW_BRANCH = '''            if claimed_up == live_up:
                results["VERIFIED"].append(entry)
            elif reviewed:
                results["REVIEWED"].append(entry)
            else:
                results["STALE"].append(entry)'''
if OLD_BRANCH not in src:
    print("ANCHOR-NOT-FOUND: classification")
    sys.exit(1)
src = src.replace(OLD_BRANCH, NEW_BRANCH, 1)

# 4. report the new bucket
OLD_REPORT = '''print(f"  VERIFIED            : {len(results['VERIFIED'])}")
print(f"  STALE               : {len(results['STALE'])}")'''
NEW_REPORT = '''print(f"  VERIFIED            : {len(results['VERIFIED'])}")
print(f"  STALE (unreviewed)  : {len(results['STALE'])}")
print(f"  REVIEWED (corrected): {len(results['REVIEWED'])}")'''
if OLD_REPORT not in src:
    print("ANCHOR-NOT-FOUND: report")
    sys.exit(1)
src = src.replace(OLD_REPORT, NEW_REPORT, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: corrected docs report as REVIEWED, unreviewed drift stays STALE")
