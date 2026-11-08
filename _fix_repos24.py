import io
import ast

p = r"C:\abrasax\tools\abx\repos24.py"
s = io.open(p, encoding="utf-8").read()
old = 'f"https://github.com/basedgod55hjl/{name}.git"'
assert old in s, "clone url anchor missing"
s = s.replace(old, '"https://github.com/basedgod55hjl/" + name + ".git"')
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("f-string collision fixed")
