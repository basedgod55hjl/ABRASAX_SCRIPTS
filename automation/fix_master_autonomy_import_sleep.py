"""One-shot: remove the import-time `time.sleep(30)` at _MASTER_AUTONOMY.py:915.

Idempotent. Backs up to <name>.bak-YYYYMMDD-HHMM before writing.
Exit 0 = patched or already patched. Exit 1 = anchor line not found (tree moved).
"""
import os
import shutil
import sys
import time

PATH = r"C:\ABRASAX\ENGINE\abrasax_engine\_MASTER_AUTONOMY.py"
SENTINEL = "# NOTE (2026-10-17 audit): this was a bare `time.sleep(30)` at IMPORT scope,"

lines = open(PATH, encoding="utf-8").read().splitlines(keepends=True)

if any(SENTINEL in ln for ln in lines):
    print("ALREADY-PATCHED")
    sys.exit(0)

idx = next((i for i, ln in enumerate(lines) if ln.strip() == "time.sleep(30)"), None)
if idx is None:
    print("ANCHOR-NOT-FOUND: no bare 'time.sleep(30)' line at column 0")
    sys.exit(1)

# must sit between the end of main()'s loop and the `if __name__` guard
guard = next((i for i, ln in enumerate(lines) if ln.startswith("if __name__")), None)
if guard is None or not (idx < guard):
    print(f"ANCHOR-MISPLACED: sleep at {idx + 1}, guard at {None if guard is None else guard + 1}")
    sys.exit(1)

backup = PATH + time.strftime(".bak-%Y%m%d-%H%M")
shutil.copy2(PATH, backup)

replacement = [
    "    # NOTE (2026-10-17 audit): this was a bare `time.sleep(30)` at IMPORT scope,\n",
    "    # so importing this module blocked every caller 30 s before argv was parsed\n",
    "    # (documented as the reason test_engine.py skips engine.check()). It was also\n",
    "    # unreachable intent: main()'s while-loop has no break, so control never falls\n",
    "    # through to here. Removed; no runtime behaviour lost.\n",
    "    pass\n",
]

out = lines[:idx] + replacement + lines[idx + 1:]
with open(PATH, "w", encoding="utf-8", newline="") as f:
    f.writelines(out)

print(f"PATCHED line {idx + 1} -> {len(replacement)} lines; backup {os.path.basename(backup)}")
print(f"total lines {len(lines)} -> {len(out)}")
