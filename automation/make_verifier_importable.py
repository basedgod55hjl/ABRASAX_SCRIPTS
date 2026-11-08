"""Make verify_docs_live importable: guard the main body behind __main__.

The module runs its whole scan at import time. That makes it impossible to reuse
its regexes for a test -- `import verify_docs_live` performs a live sweep and prints
a report, which is what happened when check_doc_verifier tried to import it.

Two reasons this matters beyond tidiness:
  1  a test that imports the tool must not also RUN the tool against the real tree
  2  the tool cannot be unit-tested at all while importing it has side effects

Fix: wrap the scan in main() and call it only under __name__ == "__main__". The
regexes and helpers stay at module level so they remain importable.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\verify_docs_live.py"
src = open(PATH, encoding="utf-8").read()

if "def main() -> int:" in src and '__name__ == "__main__"' in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

# find the start of the imperative body
marker = 'print("=== DOC CLAIM VERIFICATION (live) ===")'
idx = src.find(marker)
if idx == -1:
    print("ANCHOR-NOT-FOUND: report header")
    sys.exit(1)

head = src[:idx]
body = src[idx:]

# indent the body by four spaces and wrap it
indented = "\n".join(
    ("    " + ln) if ln.strip() else ln
    for ln in body.rstrip("\n").splitlines()
)

# strip a trailing sys.exit(0) from the body; main() will return it
indented = indented.replace("    sys.exit(0)", "    return 0")

new = (
    head
    + "def main() -> int:\n"
    + indented
    + "\n\n\n"
    + 'if __name__ == "__main__":\n'
    + "    sys.exit(main())\n"
)

open(PATH, "w", encoding="utf-8", newline="").write(new)
print("PATCHED: scan runs only under __main__; patterns stay importable")
