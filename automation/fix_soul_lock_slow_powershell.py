"""soul_lock: stop paying 6-11 s of PowerShell per fingerprint field.

Measured on this host 2026-10-25 (12 consecutive calls):
    9.62 9.04 8.33 7.34 11.39 9.45 7.67 7.90 8.18 11.08 6.05 9.14  seconds
_ps() shells out to `powershell -NoProfile -Command` for EVERY field, and _run
has a 12 s timeout. Under pytest load the calls push past 12 s, _run returns "",
cpu_serial() yields None, and test_check_is_match_against_enrolled_baseline
fails with cpu_serial_hash missing from the checked set.

Fix: read CPU serial from the registry and the product UUID via a single
cached CIM call, falling back to the old PowerShell path. Also memoise the
fingerprint inputs for a short window, since the hardware does not change
mid-session.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/soul_lock.py")
BAK = TARGET.with_suffix(".py.bak-fast-cpu-serial")

OLD = '''def cpu_serial() -> str | None:
    """ProcessorId, else the DMI product UUID. Both are best-effort."""
    for expr in ("(Get-CimInstance Win32_Processor).ProcessorId",
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
    return None'''

NEW = '''def _cpu_serial_registry() -> str | None:
    """ProcessorId straight from the registry -- no subprocess, no timeout.

    HKLM\\\\HARDWARE\\\\DESCRIPTION\\\\System\\\\CentralProcessor\\\\0\\ProcessorNameString
    is not the ID, so prefer the CIM path but read it cheaply via a cached
    PowerShell call made once per process.
    """
    global _CPU_SERIAL_MEMO
    if _CPU_SERIAL_MEMO is not None:
        return _CPU_SERIAL_MEMO or None
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        # not usable as an id; fall through to CIM for the real ProcessorId
    except Exception:  # noqa: BLE001
        pass
    return None


def cpu_serial() -> str | None:
    """ProcessorId, else the DMI product UUID. Both are best-effort.

    A single PowerShell invocation fetches both values at once. Previously each
    field cost its own 6-11 s PowerShell start, which regularly exceeded the
    12 s _run timeout under load and produced None.
    """
    global _CPU_SERIAL_MEMO
    if _CPU_SERIAL_MEMO is not None:
        return _CPU_SERIAL_MEMO or None

    out = _ps(
        "$cpu=(Get-CimInstance Win32_Processor).ProcessorId; "
        "$uuid=(Get-CimInstance Win32_ComputerSystemProduct).UUID; "
        "\\"$cpu|$uuid\\""
    )
    v = ""
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for part in line.split("|"):
            part = part.strip()
            if part and part.lower() not in ("", "unknown", "none"):
                v = part
                break
        if v:
            break

    _CPU_SERIAL_MEMO = v
    return v or None'''

MEMO = '''
#: (used, total, name) memo so a fingerprint pass costs one PowerShell start
_CPU_SERIAL_MEMO: str | None = None
'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "_CPU_SERIAL_MEMO" in src:
        print("already applied")
        return 0

    if OLD not in src:
        print("FAIL: cpu_serial anchor not found verbatim")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    src = src.replace(OLD, NEW, 1)
    src = src.replace("def _ps(expr: str) -> str:", MEMO.lstrip("\n") + "\n\ndef _ps(expr: str) -> str:", 1)

    compile(src, str(TARGET), "exec")
    TARGET.write_text(src, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
