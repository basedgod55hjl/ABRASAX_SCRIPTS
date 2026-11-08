"""abrasax.brain._live_sections(): stop recreating the ActivityBus on every call.

The original code re-executed the activity_bus module and constructed a fresh
ActivityBus for every activity() call:

    _s = _ilu.spec_from_file_location("abx_activity_bus", _p)
    _m = _ilu.module_from_spec(_s)
    _s.loader.exec_module(_m)          # full reload, every call
    bus = _m.ActivityBus()             # cold cache, every call

Consequences observed 2026-10-25:
  * every call paid the full nvidia-smi cost (~0.6-1.1 s) because the instance
    cache was never warm
  * when that probe crossed the internal budget the section merged
    _defaults(), i.e. vram_total 0.0 -> test_activity_live failed in-suite
  * the bare `except Exception: return {}` hid the cause entirely

Fix: load the module once and keep ONE process-wide bus, so throttle windows
and the last-good cache actually apply. Cache the *module* separately from the
*bus*, and on snapshot failure fall back to the last good snapshot instead of
returning an empty dict that blanks every section.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/abrasax/brain.py")
BAK = TARGET.with_suffix(".py.bak-singleton-bus")

OLD = '''def _live_sections() -> dict:
    """ActivityBus snapshot; never raises, never blocks the HTTP thread."""
    try:
        from ENGINE.floating_brain.activity_bus import ActivityBus
    except ImportError:
        pass
    try:
        import importlib.util as _ilu
        _p = ROOT / "ENGINE" / "floating_brain" / "activity_bus.py"
        if not _p.exists():
            return {}
        _s = _ilu.spec_from_file_location("abx_activity_bus", _p)
        _m = _ilu.module_from_spec(_s)
        _s.loader.exec_module(_m)  # type: ignore[union-attr]
        bus = _m.ActivityBus()
        snap = bus.snapshot(include_live=True)
        snap.pop("panels", None)  # panels state is owned by panels.py
        return snap if isinstance(snap, dict) else {}
    except Exception:
        return {}'''

NEW = '''#: process-wide ActivityBus. Rebuilding it per call meant a cold cache every
#: time, so the slow nvidia-smi probe ran on every snapshot and occasionally
#: merged its 0.0 defaults. One instance lets throttle + last-good cache work.
_BUS = None
_BUS_MOD = None
_BUS_LOCK = threading.Lock()
_LAST_LIVE: dict = {}


def _bus():
    """Load activity_bus once and keep a single ActivityBus for the process."""
    global _BUS, _BUS_MOD
    with _BUS_LOCK:
        if _BUS is not None:
            return _BUS
        if _BUS_MOD is None:
            import importlib.util as _ilu
            _p = ROOT / "ENGINE" / "floating_brain" / "activity_bus.py"
            if not _p.exists():
                return None
            _s = _ilu.spec_from_file_location("abx_activity_bus", _p)
            _m = _ilu.module_from_spec(_s)
            _s.loader.exec_module(_m)  # type: ignore[union-attr]
            _BUS_MOD = _m
        _BUS = _BUS_MOD.ActivityBus()
        return _BUS


def _live_sections() -> dict:
    """ActivityBus snapshot; never raises, never blocks the HTTP thread."""
    global _LAST_LIVE
    try:
        bus = _bus()
        if bus is None:
            return dict(_LAST_LIVE)
        snap = bus.snapshot(include_live=True)
        snap.pop("panels", None)  # panels state is owned by panels.py
        if not isinstance(snap, dict):
            return dict(_LAST_LIVE)
        # keep the last good sections so a single bad snapshot cannot blank them
        with _BUS_LOCK:
            _LAST_LIVE = snap
        return snap
    except Exception:
        # fall back to the previous good snapshot rather than reporting {}
        return dict(_LAST_LIVE)'''

HEADER_OLD = "import time"
HEADER_NEW = "import threading\nimport time"


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "_BUS_LOCK" in src:
        print("already applied")
        return 0

    if OLD not in src:
        print("FAIL: _live_sections anchor not found verbatim")
        return 1
    if "import threading" not in src and HEADER_OLD not in src:
        print("FAIL: cannot anchor the threading import")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    src = src.replace(OLD, NEW, 1)
    if "import threading" not in src:
        src = src.replace(HEADER_OLD, HEADER_NEW, 1)

    compile(src, str(TARGET), "exec")
    TARGET.write_text(src, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
