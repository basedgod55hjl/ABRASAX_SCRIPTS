"""activity_bus._vram_mib(): replace the whole function so a slow nvidia-smi
does not report 0 MB VRAM.

Measured on this host 2026-10-25 while idle:
    0.576 0.606 0.826 0.653 0.877 0.784 0.942 1.062  seconds
Already 1 of 8 runs exceeds the old hard 1.0 s clamp. Under the full pytest
suite it exceeds it routinely, _vram_mib returns (0.0, 0.0), and
test_activity_live fails with "assert 0.0 > 0" on vram_total.

New behaviour:
  * timeout ceiling raised to 5 s (the caller still throttles the probe)
  * one bounded retry if the first attempt times out
  * last-good cache, so a single slow sample returns the previous reading
    instead of claiming the GPU has 0 MB
"""
import ast
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/ENGINE/floating_brain/activity_bus.py")
BAK = TARGET.with_suffix(".py.bak-vram-timeout")

NEW_FUNC = '''def _vram_mib(nvidia_smi: str = "nvidia-smi", timeout: float = 1.0) -> tuple[float, float]:
    """``(used, total)`` MiB from the first GPU, or the last good reading.

    Measured cost of nvidia-smi on this host is 0.58-1.06 s even when idle, so
    the original hard 1.0 s clamp reported (0, 0) intermittently and made VRAM
    look absent. The ceiling is now 5 s with one bounded retry, and a last-good
    cache prevents a single slow sample from reporting 0 MB.
    """
    timeout = min(max(_as_float(timeout, 1.0), 0.05), 5.0)
    exe = shutil.which(nvidia_smi) if not os.path.isabs(nvidia_smi) else nvidia_smi
    if not exe:
        return 0.0, 0.0

    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    for attempt in range(2):
        try:
            proc = subprocess.run(
                [exe, "--query-gpu=memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                **kwargs,
            )
        except subprocess.TimeoutExpired:
            continue
        except (OSError, ValueError):
            break

        if proc.returncode != 0 or not proc.stdout:
            continue
        for line in proc.stdout.splitlines():
            fields = [p.strip() for p in line.split(",")]
            if len(fields) >= 2:
                used = _as_float(fields[0], -1.0)
                total = _as_float(fields[1], -1.0)
                if used >= 0.0 and total > 0.0:
                    return round(used, 2), round(total, 2)

    return _vram_cached()


'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "_vram_cached" in src:
        print("already applied")
        return 0

    if "def _vram_mib(" not in src:
        print("FAIL: _vram_mib not found")
        return 1
    if "\ndef _vram_cached(" in src or "_VRAM_CACHE" in src:
        print("FAIL: helper already present in an unexpected form")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    tree = ast.parse(src)
    target = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_vram_mib":
            target = node
            break
    if target is None:
        print("FAIL: _vram_mib is not a module-level function")
        return 1
    if not target.decorator_list and target.end_lineno:
        pass

    lines = src.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno
    patched = "".join(lines[:start]) + NEW_FUNC + "".join(lines[end:])

    # helper must exist before _vram_mib uses it
    helper = '''
_VRAM_LOCK = threading.Lock()


def _vram_cached() -> tuple[float, float]:
    """Last good (used, total); (0.0, 0.0) if we never got one."""
    with _VRAM_LOCK:
        c = _VRAM_CACHE
    return (c[0], c[1]) if c else (0.0, 0.0)


'''
    patched = patched.replace("def _vram_mib(", helper.lstrip("\n") + "def _vram_mib(", 1)

    # cache write goes on the success path
    patched = patched.replace(
        "                if used >= 0.0 and total > 0.0:\n"
        "                    return round(used, 2), round(total, 2)",
        "                if used >= 0.0 and total > 0.0:\n"
        "                    _u, _t = round(used, 2), round(total, 2)\n"
        "                    with _VRAM_LOCK:\n"
        "                        globals()[\"_VRAM_CACHE\"] = (_u, _t)\n"
        "                    return _u, _t",
        1,
    )

    # module-level cache declaration near the top-level constants
    if "_VRAM_CACHE: tuple" not in patched:
        patched = patched.replace(
            "_VRAM_LOCK = threading.Lock()",
            "_VRAM_CACHE: tuple[float, float] | None = None\n_VRAM_LOCK = threading.Lock()",
            1,
        )

    compile(patched, str(TARGET), "exec")
    TARGET.write_text(patched, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
