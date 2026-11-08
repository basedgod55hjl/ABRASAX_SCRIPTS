import io
import ast

p = r"C:\abrasax\scripts\build_now.py"
s = io.open(p, encoding="utf-8").read()

old = '''    argv = list(sys.argv[1:] if argv is None else argv)
    only = argv[0] if argv else None
    dry = "--dry-run" in argv'''
new = '''    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    names = [a for a in argv if not a.startswith("--")]
    only = names[0] if names else None'''
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("flag parsing fixed")
