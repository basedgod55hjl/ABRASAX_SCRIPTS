"""Fix the JSON guard with a test that proves it fires.

diagnose_json_guard.py established the mechanism:

    line:   {"gpu":"...","steps":1084,
    m.start() points at the colon
    ln[:m.start()] == '{"gpu":"...","steps"'      <- ends with a QUOTE, not a colon

so `KEY_BEFORE = r'"\\s*:\\s*$'` never matched. The guard was dead code and the
JSON numbers passed straight through.

The reliable signal is much simpler: is the character immediately before the colon
a quote? That is exactly the JSON `"key":value` shape, and it does not occur in a
legitimate endpoint reference like `127.0.0.1:9700` or `| :9626 |`.

This rewrites the guard as a direct character test, and asserts it on six real
lines taken from this repo -- two of which must be rejected, four accepted.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\reconcile_ports.py"
src = open(PATH, encoding="utf-8").read()

if "is_json_value" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. replace the dead KEY_BEFORE with a real predicate
OLD_GUARD = """COLON_PORT = re.compile(r":(\\d{4,5})\\b")
KEY_BEFORE = re.compile(r'"\\s*:\\s*$')"""
NEW_GUARD = '''COLON_PORT = re.compile(r":(\\d{4,5})\\b")


def is_json_value(line: str, colon_pos: int) -> bool:
    """True if the number is a JSON field VALUE, e.g. `"steps":1084`.

    The character immediately before the colon decides it. A JSON key ends with a
    closing quote; an endpoint reference ends with a digit, a word character, a
    space or a pipe:

        127.0.0.1:9700   -> '1'   not JSON
        | :9626 |        -> ' '   not JSON
        "steps":1084     -> '"'   JSON
    """
    if colon_pos == 0:
        return False
    return line[colon_pos - 1] == '"'
'''

if OLD_GUARD not in src:
    print("ANCHOR-NOT-FOUND: guard block")
    sys.exit(1)
src = src.replace(OLD_GUARD, NEW_GUARD, 1)

# 2. use it
OLD_USE = """                # skip "steps":1084 / "uptime_s":6907 -- a JSON value, not a port
                if KEY_BEFORE.search(ln[:m.start()]):
                    continue"""
NEW_USE = """                # skip "steps":1084 / "uptime_s":6907 -- a JSON value, not a port
                if is_json_value(ln, m.start()):
                    continue"""
if OLD_USE not in src:
    print("ANCHOR-NOT-FOUND: guard use")
    sys.exit(1)
src = src.replace(OLD_USE, NEW_USE, 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: guard now tests the character before the colon")

# ---- prove it on real lines ---------------------------------------------
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")
import importlib
import reconcile_ports as rp  # noqa: E402
importlib.reload(rp)

CASES = [
    ('{"gpu":"NVIDIA GeForce GTX 1660 Ti","live":true,"steps":1084,', 1084, True),
    ('{"status":"ok","version":"0.4.0","webhook_hmac":false,"uptime_s":6907}', 6907, True),
    ('| renderer | :9700 | OPEN |', 9700, False),
    ('gateway on 127.0.0.1:9001', 9001, False),
    ('| :9626 | DOWN |', 9626, False),
    ('curl http://127.0.0.1:1234/v1/models', 1234, False),
]

print(f"\n{'line':58s} {'port':>6} {'json?':>6} {'want':>6}  result")
fails = 0
for ln, port, want_json in CASES:
    m = rp.COLON_PORT.search(ln)
    got = int(m.group(1)) if m else None
    isj = rp.is_json_value(ln, m.start()) if m else None
    good = (got == port) and (isj == want_json)
    if not good:
        fails += 1
    print(f"{ln[:56]:58s} {got if got else '-':>6} {str(isj):>6} {str(want_json):>6}  "
          f"{'ok' if good else 'WRONG'}")

print(f"\n{len(CASES) - fails}/{len(CASES)} real lines classified correctly")
sys.exit(0 if fails == 0 else 1)
