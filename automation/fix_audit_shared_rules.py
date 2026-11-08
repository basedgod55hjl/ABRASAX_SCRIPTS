"""Point audit_config_secrets.py at the shared secret classifier.

Measured: the audit reported three 'secret literals' that the redactor had already
learned to skip:

    CONFIG/source-config/_source/hexforge_build.json:67  sk-you...re
    ...:79  sk-you...re
    ...:91  sk-you...re

They are `sk-your-key-here` documentation placeholders. Two independent copies of
"what is a secret" is how the audit and the redactor drifted apart; this makes both
use SCRIPTS/automation/secret_rules.py.

Twelfth false red tonight.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_config_secrets.py"
src = open(PATH, encoding="utf-8").read()

if "from secret_rules import" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# 1. import the shared classifier
anchor = "from collections import defaultdict"
if anchor not in src:
    print("ANCHOR-NOT-FOUND: defaultdict import")
    sys.exit(1)

src = src.replace(
    anchor,
    anchor + "\n\n"
    "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
    "from secret_rules import classify, mask  # noqa: E402  (shared with the redactor)",
    1)

# 2. use it instead of the local heuristic
OLD = '''            for m in TOKEN.finditer(line):
                tok = m.group(0)
                if tok.startswith(pre) and lo <= len(tok) <= hi:
                    # an os.environ read is not a literal
                    if "environ" in line or "getenv" in line or "process.env" in line:
                        continue
                    literals.append((os.path.relpath(full, ROOT), line_no,
                                     tok[:6] + "..." + tok[-2:]))
                    break'''

NEW = '''            for m in TOKEN.finditer(line):
                tok = m.group(0)
                if not (tok.startswith(pre) and lo <= len(tok) <= hi):
                    continue
                # an os.environ read is not a literal
                if "environ" in line or "getenv" in line or "process.env" in line:
                    continue
                # Shared classifier: placeholders such as sk-your-key-here are
                # documentation, not credentials.
                _prefix, is_secret, _why = classify(tok)
                if not is_secret:
                    break
                literals.append((os.path.relpath(full, ROOT), line_no, mask(tok)))
                break'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: literal scan")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: audit now uses secret_rules.classify")
