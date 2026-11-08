"""Fix check_winproc's last assertion: it searched for the wrong thing.

The check was:

    "timeout" not in open(winproc.__file__).read()

winproc.py legitimately uses `timeout` as a PARAMETER NAME throughout
(wait_for_exit(p, timeout=...)). Searching the whole file for the substring flags
its own API and can never pass.

What actually matters is narrower: the module must not SHELL OUT to timeout.exe.
So look for the executable invocation, not the word.

(Sixteenth false red tonight -- and the same root cause as every other one:
the check tested something other than the property it claimed to test.)
"""
import re
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\check_winproc.py"
src = open(PATH, encoding="utf-8").read()

if "SHELLS_OUT" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''check("winproc does not shell out to timeout.exe",
      "timeout" not in open(winproc.__file__, encoding="utf-8").read(),
      "no dependency on the broken utility")'''

NEW = '''# The property is "does not INVOKE timeout.exe", not "never contains the word
# timeout" -- the module legitimately has a `timeout` parameter on five functions.
_SRC = open(winproc.__file__, encoding="utf-8").read()
SHELLS_OUT = bool(re.search(r"(timeout(\\.exe)?\\s+/t\\b|subprocess[^\\n]*timeout\\.exe)",
                            _SRC))
check("winproc does not invoke timeout.exe", not SHELLS_OUT,
      "no dependency on the utility that fails without a console")

# and prove the primitives avoid shell=True entirely
check("winproc never uses shell=True", "shell=True" not in _SRC,
      "no cmd.exe intermediary")'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: timeout assertion")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
if "import re" not in src.split("import winproc")[0]:
    src = src.replace("import os\n", "import os\nimport re\n", 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: assertion now checks for invocation, not the substring")
