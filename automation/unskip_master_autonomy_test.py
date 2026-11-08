"""Replace the stale `@pytest.mark.skip` on test_master_autonomy_imports with a real
assertion, now that _MASTER_AUTONOMY.py:915 no longer sleeps at import scope.

Idempotent and safe to re-run. Exit 0 = patched or already patched / nothing to do,
1 = file structure changed in a way this script does not understand.
"""
import re
import shutil
import sys
import time

PATH = r"C:\ABRASAX\TESTS\python\test_engine.py"
MARK = "test_master_autonomy_imports"
DONE_SENTINEL = '"""Importing the autonomy module is fast and yields the engine HEX.'

src = open(PATH, encoding="utf-8").read()

if DONE_SENTINEL in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

anchor_start = src.find("@pytest.mark.skip(")
if anchor_start == -1:
    # No skip marker at all: either already migrated or someone rewrote the file.
    if f"def {MARK}" in src:
        print("NO-SKIP-MARKER: test already runs unconditionally; nothing to do")
        sys.exit(0)
    print(f"ANCHOR-NOT-FOUND: no @pytest.mark.skip( and no def {MARK}")
    sys.exit(1)

fn_at = src.find(f"def {MARK}", anchor_start)
if fn_at == -1:
    print(f"ANCHOR-NOT-FOUND: no def {MARK} after the skip")
    sys.exit(1)

new_block = (
    f"def {MARK}():\n"
    '    """Importing the autonomy module is fast and yields the engine HEX.\n'
    "\n"
    "    Regression guard: `_MASTER_AUTONOMY.py` used to run a bare `time.sleep(30)` at\n"
    "    module scope, so every import blocked 30 s and `engine.check()` could not include\n"
    "    it. Fixed 2026-10-17 (SCRIPTS/automation/fix_master_autonomy_import_sleep.py).\n"
    '    """\n'
    "    started = time.monotonic()\n"
    "    module = engine.load(SLEEPING_MODULE)\n"
    "    elapsed = time.monotonic() - started\n"
    "    assert module is not None\n"
    '    assert module.HEX == "4f5349524953424c58434b", module.HEX\n'
    '    assert elapsed < 10.0, f"import took {elapsed:.2f}s -- an import-time sleep is back"\n'
)

# Consume the whole old function body: from `def test_master_autonomy_imports():`
# through the `engine.load(SLEEPING_MODULE)` call, whatever whitespace it has.
old_fn = re.compile(
    r"def " + MARK + r"\(\):\n(?:\s*#[^\n]*\n)*\s*engine\.load\(SLEEPING_MODULE\)\n"
)
m = old_fn.search(src, fn_at)
if m is None:
    print(f"ANCHOR-NOT-FOUND: could not match the body of {MARK}")
    sys.exit(1)

out = src[:anchor_start] + new_block + src[m.end():]

if "\nimport time" not in out:
    out = out.replace("import pytest", "import time\n\nimport pytest", 1)

backup = PATH + time.strftime(".bak-%Y%m%d-%H%M")
shutil.copy2(PATH, backup)
with open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(out)

print(f"PATCHED; backup {backup.rsplit(chr(92), 1)[-1]}; {len(src)} -> {len(out)} bytes")
