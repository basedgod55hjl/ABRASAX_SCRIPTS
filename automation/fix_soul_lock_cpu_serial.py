"""soul_lock.cpu_serial(): don't index an unchecked empty result.

Line 82 was:
    v = _ps(expr).splitlines()[0].strip() if _ps(expr) else ""

It calls _ps() TWICE (once to test truthiness, once to index) and the guard only
covers an empty string, not a string whose first line is empty after strip().
Under load _ps can return a bare newline, and splitlines()[0] then raises
IndexError: list index out of range -- observed in the full suite:
    soul_lock.py:82 in cpu_serial -> IndexError: list index out of range
The same call worked standalone, so this is load/subprocess-timing dependent,
not a constant failure.

Fix: call once, parse defensively, never index blind.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/soul_lock.py")
BAK = TARGET.with_suffix(".py.bak-cpu-serial-guard")

OLD = """    for expr in ("(Get-CimInstance Win32_Processor).ProcessorId",
                 "(Get-CimInstance Win32_ComputerSystemProduct).UUID"):
        v = _ps(expr).splitlines()[0].strip() if _ps(expr) else ""
        if v and v.lower() not in ("", "unknown", "none"):
            return v
    return None"""

NEW = """    for expr in ("(Get-CimInstance Win32_Processor).ProcessorId",
                 "(Get-CimInstance Win32_ComputerSystemProduct).UUID"):
        # Call once and parse defensively. The previous form called _ps twice and
        # indexed splitlines()[0] behind a guard that only tested the raw string,
        # so a bare-newline reply raised IndexError under load.
        out = _ps(expr)
        v = ""
        if out:
            for line in out.splitlines():
                line = line.strip()
                if line:
                    v = line
                    break
        if v and v.lower() not in ("", "unknown", "none"):
            return v
    return None"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "parse defensively" in src:
        print("already applied")
        return 0

    if OLD not in src:
        print("FAIL: anchor not found verbatim")
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
