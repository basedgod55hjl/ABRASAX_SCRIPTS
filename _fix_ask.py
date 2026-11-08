import io

p = r"C:\abrasax\tools\abx\ask.py"
s = io.open(p, encoding="utf-8").read()
# The plan system prompt contains literal JSON braces; double them so str.format
# only substitutes {tools}. Do it at the definition, once.
old = '    \'{"thought": "<one sentence>", "tool": "<exact tool name from the list>", "args": {}}\\n\''
new = '    \'{{"thought": "<one sentence>", "tool": "<exact tool name from the list>", "args": {{}}}}\\n\''
assert old in s, "anchor not found"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
import ast
ast.parse(s)
print("patched ok")
