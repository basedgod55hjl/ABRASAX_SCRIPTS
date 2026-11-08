"""activity_bus: give the VRAM probe a budget it can actually meet.

Root cause of the persistent `vram_total == 0.0`:

    LIVE_BUDGET_S = 0.8            (activity_bus.py:90)
    nvidia-smi wall time, idle   = 0.58 .. 1.06 s   (measured)

_refresh_live() starts the probes on threads and joins them with an overall
deadline of `started + LIVE_BUDGET_S`. nvidia-smi routinely overshoots 0.8 s, so
the thread is abandoned, `results` has no "system_vram" entry, and the section
merges its default -- which is `vram_total: 0.0`. The inner timeout in
_vram_mib was never the binding constraint.

Fix: VRAM runs on its own slower throttle with its own budget, so a slow
nvidia-smi can never be cut off by the fast CPU/RAM budget. It is still bounded
and still cannot stack on other probes.
"""
import ast
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/ENGINE/floating_brain/activity_bus.py")
BAK = TARGET.with_suffix(".py.bak-live-budget")

OLD_BUDGET = "LIVE_BUDGET_S = 0.8"
NEW_BUDGET = """LIVE_BUDGET_S = 0.8
#: VRAM (nvidia-smi) is an order of magnitude slower than CPU/RAM: measured
#: 0.58-1.06 s on an idle GTX 1660 Ti. It gets its own budget so the fast
#: probes' 0.8 s deadline cannot abandon it and report 0 MB.
VRAM_BUDGET_S = 3.0"""

OLD_VRAM_TASK = '''                tasks.append(("system_vram", "system", lambda: (
                    _sample_vram(self.nvidia_smi, 1.0), True)))'''
NEW_VRAM_TASK = '''                tasks.append(("system_vram", "system", lambda: (
                    _sample_vram(self.nvidia_smi, 3.0), True)))'''

OLD_DEADLINE = "                deadline = started + LIVE_BUDGET_S"
NEW_DEADLINE = """                # A slow VRAM probe must not be cut off by the fast budget.
                _budget = LIVE_BUDGET_S
                if any(t[0] == "system_vram" for t in tasks):
                    _budget = max(LIVE_BUDGET_S, VRAM_BUDGET_S)
                deadline = started + _budget"""

OLD_JOIN = """                for thread in threads:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    thread.join(remaining)"""
NEW_JOIN = """                for thread in threads:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    thread.join(remaining)
                # Threads abandoned earlier may still land their result; give the
                # VRAM worker a final instant so a just-missed sample is kept.
                for thread in threads:
                    if thread.is_alive() and thread.name.endswith("system_vram"):
                        thread.join(0.75)"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "VRAM_BUDGET_S" in src:
        print("already applied")
        return 0

    for name, old in (("LIVE_BUDGET_S", OLD_BUDGET), ("vram task", OLD_VRAM_TASK),
                      ("deadline", OLD_DEADLINE), ("join loop", OLD_JOIN)):
        if old not in src:
            print(f"FAIL: {name} anchor not found verbatim")
            return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    src = src.replace(OLD_BUDGET, NEW_BUDGET, 1)
    src = src.replace(OLD_VRAM_TASK, NEW_VRAM_TASK, 1)
    src = src.replace(OLD_DEADLINE, NEW_DEADLINE, 1)
    src = src.replace(OLD_JOIN, NEW_JOIN, 1)

    ast.parse(src)  # syntax gate before writing
    TARGET.write_text(src, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
