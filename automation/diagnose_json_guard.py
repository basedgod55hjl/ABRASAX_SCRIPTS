"""Test the JSON-key rejection directly instead of assuming it works.

reconcile_ports still lists :1084 and :6907 as doc-only ports, which are the JSON
tails `"steps":1084` and `"uptime_s":6907`. The guard is:

    KEY_BEFORE = re.compile(r'"\\s*:\\s*$')
    if KEY_BEFORE.search(ln[:m.start()]): continue

and COLON_PORT matches the colon, so m.start() points AT the colon while the guard
tests the text BEFORE it -- which ends with the quote of `"steps"`, not with a
colon. The guard can therefore never fire.

Test it against the real lines before touching anything.
"""
import re
import sys

KEY_BEFORE = re.compile(r'"\s*:\s*$')
COLON_PORT = re.compile(r":(\d{4,5})\b")

CASES = [
    ('{"gpu":"NVIDIA GeForce GTX 1660 Ti","live":true,"steps":1084,', 1084),
    ('{"status":"ok","version":"0.4.0","auth":"open","webhook_hmac":false,"uptime_s":6907}', 6907),
    ('| renderer | :9700 | OPEN |', 9700),
    ('gateway on 127.0.0.1:9001', 9001),
    ('| :9626 | DOWN |', 9626),
    ('curl http://127.0.0.1:1234/v1/models', 1234),
]

print(f"{'line':62s} {'found':>6} {'guard':>6}  expected")
for ln, expected in CASES:
    m = COLON_PORT.search(ln)
    found = int(m.group(1)) if m else None
    guard = bool(m and KEY_BEFORE.search(ln[:m.start()]))
    print(f"{ln[:60]:62s} {found if found else '-':>6} {str(guard):>6}  {expected}")

print("\n--- fixed guard ---")
# A JSON value is one preceded by  "  :   with no further colon between
FIXED = re.compile(r'"\s*:[^"]*$')


def is_json_value(ln: str, pos: int) -> bool:
    """True if the number at pos is the value of a JSON key."""
    before = ln[:pos]
    # the nearest structural quote pair before the number
    return bool(re.search(r'"\s*:\s*$', before)) or before.rstrip().endswith('":')

print(f"{'line':62s} {'found':>6} {'json?':>6}  expected")
for ln, expected in CASES:
    m = COLON_PORT.search(ln)
    found = int(m.group(1)) if m else None
    j = is_json_value(ln, m.start()) if m else False
    print(f"{ln[:60]:62s} {found if found else '-':>6} {str(j):>6}  {expected}")

# the decisive test: what IS ln[:m.start()] for a JSON case?
ln = '{"gpu":"...","steps":1084,'
m = COLON_PORT.search(ln)
print(f"\nfor the JSON case: ln[:m.start()] = {ln[:m.start()]!r}")
print(f"KEY_BEFORE matches that? {bool(KEY_BEFORE.search(ln[:m.start()]))}")
print("\nThat is why the guard never fires: the colon is consumed by COLON_PORT,")
print("so the prefix ends with the KEY TEXT, not with a colon.")
sys.exit(0)
