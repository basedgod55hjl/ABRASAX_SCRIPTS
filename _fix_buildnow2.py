import io
import ast

p = r"C:\abrasax\scripts\build_now.py"
s = io.open(p, encoding="utf-8").read()

old = '''    out = _publish(row, dest)
        results.append(out)'''
# (indent-safe replace)
old = old.replace("    out = _publish", "        out = _publish")
new = '''        out = _publish(row, dest)
        results.append(out)'''
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("indent normalised")
