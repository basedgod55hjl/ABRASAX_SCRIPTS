"""Fix the malformed combined PowerShell call in soul_lock.cpu_serial().

The previous patch wrapped the expression in double quotes inside an already
double-quoted shell command:
    powershell -NoProfile -Command "$cpu=...; "$cpu|$uuid""
which the shell splits, giving rc=255 and empty output -> cpu_serial() None.

Single quotes are legal inside a double-quoted PowerShell argument and are not
special to cmd.exe, so they survive both layers.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/soul_lock.py")
BAK = TARGET.with_suffix(".py.bak-ps-quoting")

OLD = '''    out = _ps(
        "$cpu=(Get-CimInstance Win32_Processor).ProcessorId; "
        "$uuid=(Get-CimInstance Win32_ComputerSystemProduct).UUID; "
        "\\"$cpu|$uuid\\""
    )'''

NEW = '''    # Single quotes for the output string: safe through both cmd.exe and
    # PowerShell, unlike nested double quotes which the shell splits.
    out = _ps(
        "$cpu=(Get-CimInstance Win32_Processor).ProcessorId; "
        "$uuid=(Get-CimInstance Win32_ComputerSystemProduct).UUID; "
        "'{0}|{1}' -f $cpu,$uuid"
    )'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "|{1}' -f $cpu,$uuid" in src:
        print("already applied")
        return 0

    if OLD not in src:
        print("FAIL: anchor not found verbatim")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    src = src.replace(OLD, NEW, 1)
    compile(src, str(TARGET), "exec")
    TARGET.write_text(src, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
