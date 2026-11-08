"""One-shot: pin the clean-restart case in the verifier's tests."""
from pathlib import Path

T = Path(r"C:\abrasax\tests\test_verify_stack_run.py")
src = T.read_text(encoding="utf-8")

OLD_DOC = """3. 16:37Z -- two spawner pairs outlived the 2.5 s settle window, so process
   counting cannot prove "one ticker" at any affordable cost. Fix: the ledger.
   Every tick records its pid; the last three ticks must share one pid.
"""
NEW_DOC = """3. 16:37Z -- two spawner pairs outlived the 2.5 s settle window, so process
   counting cannot prove "one ticker" at any affordable cost. Fix: the ledger.
   Every tick records its pid, and the pids ticking inside ONE interval must
   agree.
4. 17:17Z -- "two tickers" was reported for a clean handover (38232 -> 12632):
   the last three tick *rows* spanned the restart. Fix: compare time, not row
   position -- a dead predecessor's final tick is outside the live window.
"""

NEW_TESTS = '''
def test_a_clean_restart_is_not_a_second_ticker(tmp_path):
    """17:17Z measured FAIL: a dead predecessor's last tick sat beside the new pid."""
    mod = _load()
    mod.LEDGER = _ledger(tmp_path, [
        {"event": "tick", "pid": 38232, "ts": "2026-11-01T17:07:03Z", "tick_interval_s": 30},
        {"event": "tick", "pid": 38232, "ts": "2026-11-01T17:07:45Z", "tick_interval_s": 30},
        {"event": "tick", "pid": 12632, "ts": "2026-11-01T17:13:28Z", "tick_interval_s": 30},
        {"event": "tick", "pid": 12632, "ts": "2026-11-01T17:13:58Z", "tick_interval_s": 30},
    ])
    assert mod._last_tick_pids(3) == [12632]


def test_a_rival_ticking_after_the_restart_is_still_caught(tmp_path):
    mod = _load()
    mod.LEDGER = _ledger(tmp_path, [
        {"event": "tick", "pid": 12632, "ts": "2026-11-01T17:13:28Z", "tick_interval_s": 30},
        {"event": "tick", "pid": 999, "ts": "2026-11-01T17:13:31Z", "tick_interval_s": 30},
    ])
    assert mod._last_tick_pids(3) == [999, 12632]


def test_a_ledger_without_timestamps_falls_back_to_the_last_rows(tmp_path):
    mod = _load()
    mod.LEDGER = _ledger(tmp_path, [
        {"event": "tick", "pid": 7},
        {"event": "tick", "pid": 7},
        {"event": "tick", "pid": 8},
    ])
    assert mod._last_tick_pids(2) == [7, 8]
'''

if "test_a_clean_restart_is_not_a_second_ticker" not in src:
    assert src.count(OLD_DOC) == 1
    src = src.replace(OLD_DOC, NEW_DOC, 1)
    anchor = '\n\n# ---- recovering services'
    assert src.count(anchor) == 1
    src = src.replace(anchor, NEW_TESTS + anchor, 1)
    T.write_text(src, encoding="utf-8", newline="")
    print("patched", T)
else:
    print("already applied")
