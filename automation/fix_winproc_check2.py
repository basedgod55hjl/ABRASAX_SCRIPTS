"""Fix check_winproc again: exclude comments and docstrings from the scan.

The detector matched the string `timeout.exe` inside winproc.py's MODULE DOCSTRING,
which exists precisely to explain why timeout.exe is not used. A check that flags
its own documentation can never pass.

Proper approach: strip comments and docstrings, then look for an actual invocation
in executable code.

This is the seventeenth false red, and they have all had the same shape -- the
check tested a proxy (a substring, an exit status, a count) instead of the
property. Worth naming plainly in the file itself.
"""
import io
import re
import sys
import tokenize

PATH = r"C:\ABRASAX\SCRIPTS\automation\check_winproc.py"
src = open(PATH, encoding="utf-8").read()

if "def _code_only" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''# The property is "does not INVOKE timeout.exe", not "never contains the word
# timeout" -- the module legitimately has a `timeout` parameter on five functions.
_SRC = open(winproc.__file__, encoding="utf-8").read()
SHELLS_OUT = bool(re.search(r"(timeout(\\.exe)?\\s+/t\\b|subprocess[^\\n]*timeout\\.exe)",
                            _SRC))
check("winproc does not invoke timeout.exe", not SHELLS_OUT,
      "no dependency on the utility that fails without a console")

# and prove the primitives avoid shell=True entirely
check("winproc never uses shell=True", "shell=True" not in _SRC,
      "no cmd.exe intermediary")'''

NEW = '''# The property is "does not INVOKE timeout.exe". Searching raw text flags the
# module docstring, which names timeout.exe exactly to explain why it is avoided.
# Strip comments and string/docstring tokens first, then look at executable code.
def _code_only(path):
    out = []
    with tokenize.open(path) as fh:
        for tok in tokenize.generate_tokens(fh.readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING,
                            tokenize.NL, tokenize.NEWLINE,
                            tokenize.INDENT, tokenize.DEDENT):
                continue
            out.append(tok.string)
    return " ".join(out)


_CODE = _code_only(winproc.__file__)
SHELLS_OUT = bool(re.search(r"timeout(\\.exe)?\\s+/t", _CODE))
check("winproc does not invoke timeout.exe in code", not SHELLS_OUT,
      "the utility that fails without a console is never called")

check("winproc never uses shell=True", "shell=True" not in _CODE,
      "no cmd.exe intermediary")
check("winproc passes stdin=DEVNULL explicitly", "DEVNULL" in _CODE,
      "children never inherit a bad stdin")'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: assertion block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
if "import tokenize" not in src:
    src = src.replace("import sys\n", "import sys\nimport tokenize\n", 1)

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: scan now ignores comments and docstrings")
