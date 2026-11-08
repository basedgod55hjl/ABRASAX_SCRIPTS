from pathlib import Path

p = Path(r"C:\abrasax\tests\test_supervisor_lmstudio_autostart.py")
s = p.read_text(encoding="utf-8")
old = '''    assert spec, "a dead LM Studio server still has no path back"
    assert [Path(str(c)).name.lower() for c in spec["cmd"][:1]] == ["lms.exe"]
    assert [str(a).lower() for a in spec["cmd"][1:]] == ["server", "start"]
    assert spec["required_bind"] == 1234'''
new = '''    assert spec, "a dead LM Studio server still has no path back"
    # The launch of record is the wrapper (it recreates the temp dir the raw CLI
    # leaves missing); the CLI itself is the declared prerequisite.
    assert [Path(str(c)).name.lower() for c in spec["cmd"][:1]] == ["python.exe"]
    assert [Path(str(c)).name.lower() for c in spec["cmd"][1:]] == ["lmstudio_start.py"]
    assert spec["required_bind"] == 1234'''
assert s.count(old) == 1
p.write_text(s.replace(old, new, 1), encoding="utf-8", newline="")
print("test updated")
