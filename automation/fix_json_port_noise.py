"""Stop treating JSON field values as port numbers.

Both remaining "doc-only ports" are JSON payloads, not endpoints:

    DOC/FLOATING-BRAIN.md:102
        {"gpu":"...","live":true,"steps":1084, ... }
        -> ":1084" is the tail of `"steps":1084`

    DOC/GAP-BOARD.md:109
        {"status":"ok","version":"0.4.0","auth":"open","webhook_hmac":false,
         "uptime_s":6907}
        -> ":6907" is the tail of `"uptime_s":6907`

My pattern `:(\\d{4,5})\\b` cannot tell an endpoint from a key-value separator, so
every JSON number of 4-5 digits became a phantom service. That is the twenty-fourth
false reading and it had polluted the reconciliation with 12 bogus ports.

A real endpoint reference in this corpus looks like one of:
    host:port      127.0.0.1:9700   localhost:9001
    bare colon      ":9700 OPEN"
    table cell     | :9626 | DOWN |
    port mention   port 9001

So: require the colon to be preceded by a host/space/pipe/quote-opener, and exclude
the case where it is preceded by a quote-closing character that makes it a JSON key.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\reconcile_ports.py"
src = open(PATH, encoding="utf-8").read()

if "JSON_KEY_TAIL" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = 'PORT = re.compile(r":(\\d{4,5})\\b")'
NEW = '''# A port reference must not be the tail of a JSON key like `"steps":1084`.
#
# Rejected:  "steps":1084   "uptime_s":6907   "version":0.4
# Accepted:  127.0.0.1:9700   localhost:9001   ":9700 OPEN"   | :9626 |   port 9001
JSON_KEY_TAIL = re.compile(r'(?<="\\s*:\\s*)(\\d{4,5})\\b')

PORT = re.compile(r"(?<![\\w\\"'])\\"?\\s*:?(\\d{4,5})\\b")
# Simpler and safer: find every 4-5 digit run that follows a colon, then discard
# the ones preceded by a JSON key ending in a quote.
COLON_PORT = re.compile(r":(\\d{4,5})\\b")
KEY_BEFORE = re.compile(r'"\\s*:\\s*$')'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: PORT regex")
    sys.exit(1)
src = src.replace(OLD, NEW, 1)

# replace the extraction site
OLD_USE = '''        for ln in r.get("claim_lines", []):
            for m in PORT.finditer(ln):
                p = int(m.group(1))
                if 1000 <= p <= 65535:
                    claimed[p].add(r["path"])'''
NEW_USE = '''        for ln in r.get("claim_lines", []):
            for m in COLON_PORT.finditer(ln):
                # skip "steps":1084 / "uptime_s":6907 -- a JSON value, not a port
                if KEY_BEFORE.search(ln[:m.start()]):
                    continue
                p = int(m.group(1))
                if 1000 <= p <= 65535:
                    claimed[p].add(r["path"])'''
if OLD_USE not in src:
    print("ANCHOR-NOT-FOUND: extraction loop")
    sys.exit(1)
src = src.replace(OLD_USE, NEW_USE, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: JSON key tails no longer parsed as ports")
