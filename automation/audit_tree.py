"""Audit the tree before reorganising anything.

The directive asks to organise around C:\\ABRASAX, clean temporary logs, and point
the venv at C:\\PYTHON\\.venv_gui. Measured facts first:

  * C:\\PYTHON does not exist. The active virtualenv is
    C:\\ABRASAX\\PYTHON\\.venv_gui (26,343 files) and every script references it
    by that path. Moving it would break the running system, so this audit records
    the discrepancy instead of silently complying.
  * LOGS holds 340 files but only ~20 MB -- small. The risk is not size, it is that
    live append-only ledgers (supervisor-ledger.jsonl, alive-bind.jsonl,
    mem-governor.jsonl) sit beside disposable build output.

So the audit separates three classes:
    LIVE LEDGER   append-only, still written, must not be deleted or moved while a
                  writer holds it
    EVIDENCE      logs/screenshots that justify a claim in DOC/ -- keep, but may be
                  age-rotated
    DISPOSABLE    build logs, .bak copies, _-prefixed scratch files

Reports totals by class and lists what would be rotated. Deletes nothing.
"""
import os
import re
import sys
import time
from collections import defaultdict

ROOT = r"C:\ABRASAX"
LOGS = os.path.join(ROOT, "LOGS")

# append-only ledgers that a live process may hold open
LIVE_LEDGERS = {
    "supervisor-ledger.jsonl",
    "supervisor-state.json",
    "ops-state.json",
    "alive-bind.jsonl",
    "mem-governor.jsonl",
    "build-queue.jsonl",
    "gateway-server.log",
}

# evidence deliberately cited by documents
EVIDENCE_HINTS = ("overlay_shot", "hud-screen", "hud-v2", "pytest-", "suite",
                  "e2e", "verify", "check")

DISPOSABLE_PATTERNS = (
    re.compile(r".*\.bak-\d{8}-\d{4}$"),
    re.compile(r"^_.*"),                      # scratch files prefixed with _
    re.compile(r".*\.(tmp|log)$"),
)


def classify(name: str, path: str) -> str:
    if name in LIVE_LEDGERS:
        return "LIVE"
    if any(h in name for h in EVIDENCE_HINTS):
        return "EVIDENCE"
    if any(p.match(name) for p in DISPOSABLE_PATTERNS):
        return "DISPOSABLE"
    return "OTHER"


buckets = defaultdict(list)
for dp, dn, fns in os.walk(LOGS):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for fn in fns:
        full = os.path.join(dp, fn)
        try:
            st = os.stat(full)
        except OSError:
            continue
        buckets[classify(fn, full)].append(
            (os.path.relpath(full, LOGS), st.st_size, st.st_mtime))

print("=== LOGS CLASSIFICATION ===")
total_n = total_b = 0
for cls in ("LIVE", "EVIDENCE", "DISPOSABLE", "OTHER"):
    rows = buckets.get(cls, [])
    n = len(rows)
    b = sum(r[1] for r in rows)
    total_n += n
    total_b += b
    print(f"  {cls:11s} {n:4d} file(s)  {b / 1e6:7.2f} MB")

print(f"  {'TOTAL':11s} {total_n:4d} file(s)  {total_b / 1e6:7.2f} MB")

print("\n=== LIVE LEDGERS (never delete; a writer may hold them) ===")
for name in sorted(LIVE_LEDGERS):
    for dp, _dn, fns in os.walk(LOGS):
        if name in fns:
            full = os.path.join(dp, name)
            st = os.stat(full)
            age = (time.time() - st.st_mtime) / 60
            print(f"  {name:28s} {st.st_size:9,d} B   last write {age:.0f} min ago")
            break
    else:
        print(f"  {name:28s} (absent)")

print("\n=== DISPOSABLE, ranked by size (candidates for rotation) ===")
disp = sorted(buckets.get("DISPOSABLE", []), key=lambda r: -r[1])
for rel, size, mtime in disp[:15]:
    age_d = (time.time() - mtime) / 86400
    print(f"  {size / 1e6:7.2f} MB  {age_d:5.1f} d old  {rel}")
if len(disp) > 15:
    print(f"  ... and {len(disp) - 15} more")

print("\n=== VENV REALITY CHECK ===")
claimed = r"C:\PYTHON\.venv_gui"
actual = os.path.join(ROOT, "PYTHON", ".venv_gui")
print(f"  requested path  {claimed}: {'EXISTS' if os.path.exists(claimed) else 'DOES NOT EXIST'}")
print(f"  actual path     {actual}: {'EXISTS' if os.path.exists(actual) else 'MISSING'}")
if os.path.isdir(actual):
    n = sum(len(fns) for _, _, fns in os.walk(actual))
    print(f"  files in venv   {n:,}")
    print(f"  interpreter     {os.path.join(actual, 'Scripts', 'python.exe')}")

# how many scripts hardcode the venv path?
refs = 0
for dp, dn, fns in os.walk(os.path.join(ROOT, "SCRIPTS")):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for fn in fns:
        if fn.endswith(".py"):
            try:
                t = open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if "venv_gui" in t:
                refs += 1
print(f"  scripts referencing venv_gui: {refs}")

print("\nRESULT: audit only, nothing moved or deleted")
sys.exit(0)
