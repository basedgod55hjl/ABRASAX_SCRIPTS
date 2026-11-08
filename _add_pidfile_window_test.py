from pathlib import Path

p = Path(r"C:\abrasax\tests\test_supervisor_pidfile_race.py")
s = p.read_text(encoding="utf-8")

extra = '''

def test_an_empty_pidfile_mid_write_is_not_stolen(tmp_path, monkeypatch):
    """The O_EXCL create and the pid write are two steps; the gap is not a corpse.

    Measured 2026-11-01 under load: a loser read the empty file, unlinked the
    winner's lock and created its own - two winners from an atomic claim. The
    test passes a live foreign pid in after 0.2 s, exactly like a winner that is
    still writing.
    """
    import threading
    import time

    mod = _load()
    pidfile = tmp_path / "supervisor.pid"
    monkeypatch.setattr(mod, "PIDFILE", pidfile)
    pidfile.write_text("", encoding="utf-8")

    with _LiveOther() as other:
        def _winner_writes():
            time.sleep(0.2)
            pidfile.write_text(str(other), encoding="utf-8")

        t = threading.Thread(target=_winner_writes)
        t.start()
        try:
            assert mod._claim_pidfile() is False, "the loser stole a mid-write lock"
        finally:
            t.join()
        assert pidfile.read_text().strip() == str(other)
'''

anchor = "\n\ndef test_a_live_owner_blocks_the_claim_and_is_not_overwritten(tmp_path):"
assert anchor in s
s = s.replace(anchor, extra + anchor, 1)
p.write_text(s, encoding="utf-8", newline="")
print("test added")
