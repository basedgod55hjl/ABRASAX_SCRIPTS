"""soul_lock.mac_address(): pick a MAC deterministically (AST replacement).

The list order from Get-CimInstance Win32_NetworkAdapter is not stable, so
"return the first MAC" made the fingerprint flap between adapters within one
process. Observed 2026-10-25:

    attempt 0,3   mac_hash = c399eb739eddd5f6
    attempt 1,2,4 mac_hash = ded5a182712821cd     (-> check() said "mismatch")

cpu_serial_hash and gpu_uuid_hash were stable, so the MAC alone caused the
intermittent failure of test_check_is_match_against_enrolled_baseline.

This replaces the whole function body by locating it with ast, avoiding fragile
string anchoring through two layers of shell quoting.
"""
import ast
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/soul_lock.py")
BAK = TARGET.with_suffix(".py.bak-stable-mac")

NEW_FUNC = '''def mac_address() -> str | None:
    """A physical adapter MAC, normalised, chosen deterministically.

    Get-CimInstance does not guarantee adapter order, so returning the first
    line made the fingerprint flap between adapters (observed mac_hash
    alternating c399eb73... / ded5a182... within one process). Sorting the
    candidates makes the same machine always produce the same value.
    """
    expr = ('Get-CimInstance Win32_NetworkAdapter -Filter "PhysicalAdapter=True" '
            '| Select-Object -ExpandProperty MACAddress')
    out = _ps(expr)
    candidates = sorted({
        bare
        for bare in (
            line.strip().replace(":", "").replace("-", "").lower()
            for line in (out or "").splitlines()
        )
        if len(bare) == 12
    })
    if candidates:
        return candidates[0]
    node = format(uuid.getnode(), "012x")
    return node if len(node) == 12 else None


'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "chosen deterministically" in src:
        print("already applied")
        return 0

    tree = ast.parse(src)
    node = next((n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "mac_address"), None)
    if node is None:
        print("FAIL: mac_address is not a module-level function")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    lines = src.splitlines(keepends=True)
    start, end = node.lineno - 1, node.end_lineno
    patched = "".join(lines[:start]) + NEW_FUNC + "".join(lines[end:])

    compile(patched, str(TARGET), "exec")
    TARGET.write_text(patched, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
