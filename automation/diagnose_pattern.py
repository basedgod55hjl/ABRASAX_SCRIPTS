"""Find out exactly why `| renderer | :9700 | OPEN |` still fails.

Rather than guess again, run the actual compiled patterns against the actual string
and print what each one sees. Twenty false reds tonight came from assumptions about
what a pattern does; this measures it.
"""
import re
import sys

sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

import verify_docs_live as vdl  # noqa: E402

CASES = [
    "| renderer | :9700 | OPEN |",
    "| phantom | :9999 | ONLINE |",
    ":9700 OPEN",
    ":9700 is OPEN",
    "gateway :9000 | CLOSED",
    "| :9626 | DOWN |",
]

print(f"STRICT_PORT = {vdl.STRICT_PORT}")
print(f"UP_WORDS    = {vdl.UP_WORDS}")
print()

for label, rx in (("ROW", vdl.ROW), ("ROW2", vdl.ROW2)):
    print(f"=== {label} ===")
    print(f"pattern: {rx.pattern}")
    for c in CASES:
        m = rx.search(c)
        if m:
            print(f"  MATCH  {c!r} -> port={m.group(1) or m.group(2)} "
                  f"word={m.group(3)!r} span={m.span()}")
        else:
            print(f"  no     {c!r}")
    print()

# why does the first case fail? show the raw pieces
c = "| renderer | :9700 | OPEN |"
for probe in (r":(\d{3,5})", r"(?::(\d{3,5}))(.*?)(OPEN)", r"(?::(\d{3,5})).{0,60}?(OPEN)"):
    m = re.search(probe, c, re.IGNORECASE)
    print(f"probe {probe!r}: {'MATCH ' + repr(m.groups()) if m else 'no match'}")

sys.exit(0)
