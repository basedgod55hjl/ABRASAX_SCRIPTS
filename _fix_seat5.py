import io
import ast

p = r"C:\abrasax\tools\abx\seat.py"
s = io.open(p, encoding="utf-8").read()

broken = '''            user = PRE + check["prompt"]
        if check.get("hint"):
            user += "\\nOPERATOR HINT: " + check["hint"]
        got = llm.chat(prompt=user, route=route, model=model,
                           system=check["system"], temperature=0.0, max_tokens=260)'''
fixed = '''            user = PRE + check["prompt"]
            if check.get("hint"):
                user += "\\nOPERATOR HINT: " + check["hint"]
            got = llm.chat(prompt=user, route=route, model=model,
                           system=check["system"], temperature=0.0, max_tokens=260)'''
assert broken in s, "broken block not found"
s = s.replace(broken, fixed, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("indent repaired")
