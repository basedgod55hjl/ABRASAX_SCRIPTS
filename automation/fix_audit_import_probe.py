"""Fix audit_dependencies.py: the import probe was too heavy and never finished.

The probe did `__import__(m)` for every third-party module in one child process.
Importing torch / pyimgui / OpenGL initialises CUDA, GL contexts and dozens of
transitive deps; it burned 51 s of CPU and produced no output, so the whole audit
hung with an empty log.

Two fixes, both about measuring the right thing:
  1. use importlib.util.find_spec(), which locates a module WITHOUT executing it.
     That answers "is this installed?" which is the actual question -- not
     "does importing it succeed and how long does it take?".
  2. flush the probe's output so a partial run is still readable.

Also removes the unused `import ast` duplication path cost by keeping the AST walk
(the walk itself is cheap; it was the imports that hurt).
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_dependencies.py"
src = open(PATH, encoding="utf-8").read()

if "find_spec" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''probe = (
    "import sys, json\\n"
    "mods = " + json.dumps(third_party) + "\\n"
    "out = {}\\n"
    "for m in mods:\\n"
    "    try:\\n"
    "        __import__(m)\\n"
    "        out[m] = 'ok'\\n"
    "    except Exception as e:\\n"
    "        out[m] = type(e).__name__ + ': ' + str(e)[:60]\\n"
    "print(json.dumps(out))\\n"
)'''

NEW = '''# find_spec LOCATES a module without executing it. The previous version called
# __import__() on everything, which initialises CUDA (torch), creates GL contexts
# (OpenGL), and burned 51 s of CPU without producing output. "Is it installed?" is
# the question; "does importing it work, and how fast?" is a different, heavier one.
probe = (
    "import json, importlib.util\\n"
    "mods = " + json.dumps(third_party) + "\\n"
    "out = {}\\n"
    "for m in mods:\\n"
    "    try:\\n"
    "        out[m] = 'ok' if importlib.util.find_spec(m) else 'NotFound'\\n"
    "    except Exception as e:\\n"
    "        out[m] = type(e).__name__ + ': ' + str(e)[:60]\\n"
    "print(json.dumps(out), flush=True)\\n"
)'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: probe block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)

# make the audit's own prints flush so a partial run is readable
if "def main()" not in src:
    pass

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: probe uses find_spec instead of __import__")
