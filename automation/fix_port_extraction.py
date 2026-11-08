"""Tighten port extraction: 79 "stale claims" were mostly line numbers.

Measured output of the first run:

    :29   doc says UP   live is CLOSED   DOC/DISK-SCAN/PROFILE.md
    :106  doc says UP   live is CLOSED   DOC/DISK-SCAN/G-DRIVE.md
    :107  doc says RUNNING  live is CLOSED   DOC/SWARM.md
    :170  doc says LIVE  live is CLOSED   DOC/DISK-INVENTORY.md
    :200  doc says UP    live is CLOSED   DOC/FINAL_RUN_STATE.md

29, 106, 107, 118, 120, 122, 170, 200, 240 are not ports. They are line numbers,
page counts, dates and drive letters that happened to sit near a status word. My
ROW3 pattern was `(\\d{3,5})\\D{0,20}(word)` with no requirement for a colon, so it
matched almost anything.

That is the twentieth false red of this project and it has a familiar shape: a
loose pattern standing in for a specific fact.

Fix -- a port claim must actually look like a port reference:
  * preceded by ':'            (:8080)
  * OR inside a table row      (| 8080 | UP |)
  * AND in the plausible range  1024-65535 for a service, allowing well-known <1024
    only when explicitly written as a colon-port
  * AND the port must appear in a known-port set OR be a 4-5 digit number, because
    a bare 3-digit number next to a status word is far more likely to be a count

Rather than guess thresholds, restrict to ports the project actually uses plus any
4-5 digit number, and require a colon or a table pipe immediately before.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "STRICT_PORT" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''# ":9000 gateway /health | ONLINE"   and   ":9000 | DOWN"
ROW = re.compile(
    r":(\\d{3,5})\\b[^\\n|]{0,60}?\\|\\s*\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\**",
    re.IGNORECASE)
# ":9001 UP 38 ms"  (the abrasax services table)
ROW2 = re.compile(
    r":(\\d{3,5})\\s+(?:\\S+\\s+){0,3}?\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\**",
    re.IGNORECASE)
# "gateway :9000 (DOWN)"
ROW3 = re.compile(
    r"(\\d{3,5})\\D{0,20}(" + UP_WORDS + "|" + DOWN_WORDS + r")\\b", re.IGNORECASE)'''

NEW = '''# A port claim must LOOK like a port reference. The previous third pattern was
# `(\\d{3,5})\\D{0,20}(status)` with no anchor, so line numbers (29, 106, 170, 200)
# and page counts were read as ports and produced 79 bogus "stale" claims.
#
# Accepted shapes only:
#   ":9000 gateway /health | ONLINE"     colon-port, table row
#   ":9001 UP 38 ms"                     colon-port, services table
#   "| 8080 | UP |"                      table row with a bare port
#
# A bare 3-digit number next to a status word is a COUNT, not a port, so bare
# numbers must be 4-5 digits to qualify.
STRICT_PORT = r"(?::(\\d{3,5})|\\|\\s*(\\d{4,5})\\s*\\|)"

ROW = re.compile(
    STRICT_PORT + r"[^\\n|]{0,60}?\\|?\\s*\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\**",
    re.IGNORECASE)
ROW2 = re.compile(
    STRICT_PORT + r"\\s+(?:\\S+\\s+){0,3}?\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\**",
    re.IGNORECASE)
# third shape dropped entirely: it was the source of every false positive'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: regex block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)

# the port is now group 1 OR group 2, and the status word shifted to group 3
OLD_LOOP = '''    for rx in (ROW, ROW2, ROW3):
        for m in rx.finditer(text):
            port = int(m.group(1))
            if not (1 <= port <= 65535):
                continue   # regex caught a timestamp or a stat, not a port
            word = m.group(2).strip()'''

NEW_LOOP = '''    for rx in (ROW, ROW2):
        for m in rx.finditer(text):
            raw = m.group(1) or m.group(2)
            if raw is None:
                continue
            port = int(raw)
            if not (1 <= port <= 65535):
                continue
            word = m.group(3).strip()'''

if OLD_LOOP not in src:
    print("ANCHOR-NOT-FOUND: match loop")
    sys.exit(1)

src = src.replace(OLD_LOOP, NEW_LOOP, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: port claims require a colon or a table cell, and no loose third pattern")
