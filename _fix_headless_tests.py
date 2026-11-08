from pathlib import Path

p = Path(r"C:\abrasax\tests\test_headless_spawns.py")
s = p.read_text(encoding="utf-8")

old1 = '''    monkeypatch.setattr(mod.winproc, "spawn", fake_spawn)
    monkeypatch.setattr(mod, "alive", lambda: True)
    monkeypatch.setattr(mod, "gpu_free", lambda: 4096)
    rc = mod.start()'''
new1 = '''    monkeypatch.setattr(mod.winproc, "spawn", fake_spawn)
    # first call is the "already serving?" guard, the wait loop after the spawn
    # must then see it alive or start() polls for 120 s
    calls = {"n": 0}

    def fake_alive():
        calls["n"] += 1
        return calls["n"] > 1

    monkeypatch.setattr(mod, "alive", fake_alive)
    monkeypatch.setattr(mod, "gpu_free", lambda: 4096)
    rc = mod.start()'''
assert s.count(old1) == 1
s = s.replace(old1, new1, 1)

old2 = '''    monkeypatch.setattr(svc.winproc, "run", fake_run, raising=False)
    if not hasattr(svc, "winproc"):
        import abrasax.winproc as w
        monkeypatch.setattr(w, "run", fake_run)'''
new2 = '''    # services imports winproc lazily inside start_stack; patch the module itself
    import abrasax.winproc as w
    monkeypatch.setattr(w, "run", fake_run)'''
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)

p.write_text(s, encoding="utf-8", newline="")
print("tests fixed")
