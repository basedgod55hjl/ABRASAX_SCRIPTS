import pathlib

p = pathlib.Path(r"C:\ABRASAX\TESTS\python\test_nervous_ui.py")
lines = p.read_text(encoding="utf-8").splitlines()

i = next(i for i, l in enumerate(lines) if "ABRAXIS WORLD MODEL" in l)
# The test asserted the masthead's exact wording. The page's identity is part of
# the contract, but the assertion should name the system correctly and not pin
# the rest of the phrase - the header has already changed twice.
lines[i] = '        assert "ABRASAX" in html, "the page must name the system"'

p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("patched nervous_ui title assertion")
