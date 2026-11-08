"""Fix .gitignore so Unreal's `Source/` folder is not excluded.

Line 87 `SOURCE/` is a publish-scope rule for the retired top-level corpus dir.
Git matches it case-insensitively on every path, so it also swallowed
APPS/unreal-brain/Source/ -- the C++ module of the UE plugin, which then could not
be committed at all.

Fix: anchor the rule to the repo root and add an explicit negation for the UE
plugin's source tree. Idempotent.
"""
import sys

PATH = r"C:\ABRASAX\.gitignore"
src = open(PATH, encoding="utf-8").read()

if "/SOURCE/" in src and "!APPS/unreal-brain/Source/" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

anchor = "SOURCE/\nTYPESCRIPT/\nVENDORS/\n/PYTHON/\nCONFIG/\nTOOLS/\n"
if anchor not in src:
    print("ANCHOR-NOT-FOUND: publish-scope block")
    sys.exit(1)

replacement = (
    "# Anchored to the repo root. An unanchored SOURCE/ also matched\n"
    "# APPS/unreal-brain/Source/ (git is case-insensitive on Windows), hiding the\n"
    "# Unreal C++ module from every commit.\n"
    "/SOURCE/\n"
    "/TYPESCRIPT/\n"
    "/VENDORS/\n"
    "/PYTHON/\n"
    "/CONFIG/\n"
    "/TOOLS/\n"
    "\n"
    "# First-party source trees that must always be committed.\n"
    "!APPS/unreal-brain/Source/\n"
    "!APPS/unreal-brain/Source/**\n"
)

src = src.replace(anchor, replacement, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: SOURCE/ anchored + UE Source/ negated")
