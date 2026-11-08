"""Update TESTS/python/test_native.py assertions to the current `abrasax test` contract.

Why: RUST/abrasax_rs/src/main.rs::cmd_test() was rewritten (2026-10-25 02:08) to
emit a per-check [OK]/[WARN] stream ending in
"[OK] Selftest complete - review [WARN] lines above."
The test (written 2026-10-17) still asserted the old REPL-only strings
"[OK] All tests passed." and "[OK] Phi score", which cmd_test() never prints.
Observed rc=0 with a full [OK] stream -- the binary is correct, the test was stale.

Idempotent. Backs up first.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/TESTS/python/test_native.py")
BAK = TARGET.with_suffix(".py.bak-native-selftest")

OLD = '''    assert "[OK] All tests passed." in res["stdout"]
    assert "[OK] Phi score" in res["stdout"]
'''

NEW = '''    # cmd_test() emits a per-check stream and a completion line. The old
    # "All tests passed." / "Phi score" strings belong to the interactive
    # terminal.rs REPL command, not to `abrasax test` -- see main.rs::cmd_test.
    out = res["stdout"]
    assert "[OK] Selftest complete" in out
    ok_checks = out.count("[OK]")
    assert ok_checks >= 3, f"expected several [OK] checks, saw {ok_checks}: {out[:400]!r}"
    assert "[TEST]" in out or "[OK]" in out
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "Selftest complete" in src:
        print("already applied - no change")
        return 0

    if OLD not in src:
        print("FAIL: anchor not found verbatim; refusing to patch blind")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    patched = src.replace(OLD, NEW, 1)
    compile(patched, str(TARGET), "exec")
    TARGET.write_text(patched, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
