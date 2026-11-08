from pathlib import Path

p = Path(r"C:\abrasax\tests\test_services_start_all.py")
s = p.read_text(encoding="utf-8")
bad = '''    built = src.count(chr(34) + "SCRIPTS" + chr(34) + " / " + chr(34) + "launchers" + chr(34) + " / " + chr(34) + "start_abrasax_stack.ps1" + chr(34));n    assert built == 1, "a second launcher path appeared"'''
good = '''    # One path expression, one launcher. (The help text names the file too;
    # what must not appear twice is a way to *start* something.)
    built = src.count('ROOT / "SCRIPTS" / "launchers" / "start_abrasax_stack.ps1"')
    assert built == 1, "a second launcher path appeared"'''
assert s.count(bad) == 1, s.count(bad)
p.write_text(s.replace(bad, good), encoding="utf-8", newline="")
print("fixed")
