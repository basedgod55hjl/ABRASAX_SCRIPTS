"""Add the missing status words. The regex was fine; the vocabulary was not.

diagnose_pattern.py proved it conclusively:

    | :9999 | ONLINE |   -> MATCH  (ONLINE is in UP_WORDS)
    | :9700 | OPEN   |   -> no match
    | :9626 | DOWN   |   -> MATCH  (DOWN is in DOWN_WORDS)
    gateway :9000 | CLOSED -> MATCH  (CLOSED is in DOWN_WORDS)

UP_WORDS   = ONLINE|LISTENING|UP|HEALTHY|RUNNING|live
DOWN_WORDS = DOWN|OFFLINE|CLOSED|STOPPED|dead

"OPEN" -- the word this project's own audit tools print for a listening socket --
is absent, while its opposite "CLOSED" is present. That asymmetry means every table
row written the way the audits write them went unparsed.

Adds OPEN to UP_WORDS, and LIVE/ALIVE (uppercase LIVE already matched only because
of the `live` alternation with IGNORECASE, which is fragile), plus NOT LISTENING,
ABSENT, MISSING to DOWN.

Ordering matters: alternation is first-match, so longer words must come first or
"LISTENING" would be matched as "LISTEN" + leftovers. UP is kept last so it cannot
shadow UPSTREAM-free cases.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "NOT LISTENING" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD_UP = 'UP_WORDS = r"(?:ONLINE|LISTENING|UP|HEALTHY|RUNNING|live)"'
NEW_UP = ('UP_WORDS = r"(?:NOT\\s+LISTENING|LISTENING|ONLINE|HEALTHY|RUNNING|'
          'OPEN|LIVE|ALIVE|UP)"')
if OLD_UP not in src:
    print("ANCHOR-NOT-FOUND: UP_WORDS")
    sys.exit(1)
src = src.replace(OLD_UP, NEW_UP, 1)

OLD_DOWN = 'DOWN_WORDS = r"(?:DOWN|OFFLINE|CLOSED|STOPPED|dead)"'
NEW_DOWN = ('DOWN_WORDS = r"(?:NOT\\s+LISTENING|OFFLINE|CLOSED|STOPPED|DOWN|'
            'DEAD|ABSENT|MISSING)"')
if OLD_DOWN not in src:
    print("ANCHOR-NOT-FOUND: DOWN_WORDS")
    sys.exit(1)
src = src.replace(OLD_DOWN, NEW_DOWN, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: UP_WORDS gains OPEN/LIVE/ALIVE; DOWN_WORDS gains ABSENT/MISSING")
print(f"  UP   = {NEW_UP}")
print(f"  DOWN = {NEW_DOWN}")
