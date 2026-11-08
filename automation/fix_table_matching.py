"""Fix two real extraction defects the injected-drift test exposed.

The test wrote a table row the way the docs actually write it:

    | renderer | :9700 | OPEN |

and the verifier did NOT see it, while it DID match a plain-prose variant twice.

DEFECT 1 -- the table shape is invisible
    ROW = STRICT_PORT + r"[^\\n|]{0,60}?\\|?\\s*\\**(status)"
    The character class `[^\\n|]` EXCLUDES the pipe. So after matching ":9700" the
    very next character, "|", terminates the intermediate part and the optional
    `\\|?` cannot recover: the status word sits one pipe later. Every claim written
    in a Markdown table -- which is most of them -- was being missed.

DEFECT 2 -- double counting
    ROW and ROW2 both matched the same prose line, reporting 9999 twice. The
    de-duplication set keys on (port, claimed_up), but the test's own helper did not
    dedupe, which is how the duplicate surfaced. The tool dedupes; the helper must
    match it.

Fix: allow pipes in the separator but not newlines, and make the separator
non-greedy with an explicit bound so it cannot run away.
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "SEP = " in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''STRICT_PORT = r"(?::(\\d{3,5})|\\|\\s*(\\d{4,5})\\s*\\|)"

ROW = re.compile(
    STRICT_PORT + r"[^\\n|]{0,60}?\\|?\\s*\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\**",
    re.IGNORECASE)
ROW2 = re.compile(
    STRICT_PORT + r"\\s+(?:\\S+\\s+){0,3}?\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\**",
    re.IGNORECASE)'''

NEW = '''STRICT_PORT = r"(?::(\\d{3,5})|\\|\\s*(\\d{4,5})\\s*\\|)"

# The separator must be allowed to CONTAIN pipes: markdown tables read
#     | renderer | :9700 | OPEN |
# so after ":9700" the next character is "|", which the previous `[^\\n|]` class
# rejected outright. Most real claims are in tables, and none of them matched.
SEP = r"(?:(?!\\n).){0,60}?"          # anything but a newline, bounded and lazy

ROW = re.compile(
    STRICT_PORT + SEP + r"(" + UP_WORDS + "|" + DOWN_WORDS + r")\\b",
    re.IGNORECASE)
ROW2 = re.compile(
    STRICT_PORT + r"\\s+(?:\\S+\\s+){0,3}?\\**(" + UP_WORDS + "|" + DOWN_WORDS + r")\\b",
    re.IGNORECASE)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: regex block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: separator may contain pipes; table rows now match")
