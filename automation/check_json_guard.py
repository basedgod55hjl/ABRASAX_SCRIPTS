"""Verify the JSON guard by extracting exact line ranges, not by regex.

The regex extraction pulled in trailing code and failed with
    NameError: name 'defaultdict' is not defined
because it swallowed the next statement.

Measured line numbers in reconcile_ports.py:
     76  COLON_PORT = re.compile(r":(\\d{4,5})\\b")
     79  def is_json_value(line: str, colon_pos: int) -> bool:
     92      return line[colon_pos - 1] == '"'

Extract 76..92 by line index, exec it, and test six real lines from this repo.
Two must be rejected as JSON values; four accepted as endpoint references.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\reconcile_ports.py"
lines = open(PATH, encoding="utf-8").read().splitlines()

# find the block boundaries by content, then take the exact slice
start = next((i for i, ln in enumerate(lines)
              if ln.startswith("COLON_PORT = re.compile")), None)
if start is None:
    print("MISSING COLON_PORT")
    sys.exit(1)

fn_start = next((i for i, ln in enumerate(lines)
                 if ln.startswith("def is_json_value")), None)
if fn_start is None:
    print("MISSING is_json_value")
    sys.exit(1)

fn_end = fn_start
while fn_end + 1 < len(lines):
    nxt = lines[fn_end + 1]
    if nxt and not nxt.startswith((" ", "\t")):
        break
    fn_end += 1

block = "\n".join(lines[start:fn_start]) + "\n" + "\n".join(lines[fn_start:fn_end + 1])
print("--- extracted ---")
print(block)
print("--- end ---\n")

ns = {"re": re}
exec(block, ns)
COLON_PORT = ns["COLON_PORT"]
is_json_value = ns["is_json_value"]

CASES = [
    ('{"gpu":"NVIDIA GeForce GTX 1660 Ti","live":true,"steps":1084,', 1084, True),
    ('{"status":"ok","version":"0.4.0","webhook_hmac":false,"uptime_s":6907}', 6907, True),
    ('| renderer | :9700 | OPEN |', 9700, False),
    ('gateway on 127.0.0.1:9001', 9001, False),
    ('| :9626 | DOWN |', 9626, False),
    ('curl http://127.0.0.1:1234/v1/models', 1234, False),
]

print(f"{'line':54s} {'port':>6} {'json?':>6} {'want':>6}  result")
fails = 0
for ln, port, want_json in CASES:
    m = COLON_PORT.search(ln)
    got = int(m.group(1)) if m else None
    isj = is_json_value(ln, m.start()) if m else None
    good = (got == port) and (isj == want_json)
    if not good:
        fails += 1
    print(f"{ln[:52]:54s} {got if got else '-':>6} {str(isj):>6} "
          f"{str(want_json):>6}  {'ok' if good else 'WRONG'}")

print(f"\n{len(CASES) - fails}/{len(CASES)} correct")
print("RESULT:", "PASS -- JSON values rejected, endpoints accepted"
      if fails == 0 else "FAIL")
sys.exit(0 if fails == 0 else 1)
