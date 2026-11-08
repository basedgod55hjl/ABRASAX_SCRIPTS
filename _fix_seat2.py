import io
import ast

p = r"C:\abrasax\tools\abx\seat.py"
s = io.open(p, encoding="utf-8").read()

# 1. Add a rubric preamble that states the voice/format in the USER turn too,
#    because some providers weight the last user message far above the system
#    prompt when deciding whether to "help" or "call".
old_rubric = 'RUBRIC: list[dict[str, Any]] = ['
new_rubric = '''PRE = ("[INSTRUMENTED SESSION] You are running inside a tool harness on the operator\\'s machine. "
       "You are not a chatbot here; you do not explain, and you never ask for clarification. "
       "Answer with the JSON object only, starting with { and ending with }. ")

RUBRIC: list[dict[str, Any]] = ['''
assert old_rubric in s
s = s.replace(old_rubric, new_rubric, 1)

# 2. Prefix every prompt with PRE in the scorer.
old_call = '''        got = llm.chat(prompt=check["prompt"], route=route, model=model,
                           system=check["system"], temperature=0.0, max_tokens=260)'''
new_call = '''        got = llm.chat(prompt=PRE + check["prompt"], route=route, model=model,
                           system=check["system"], temperature=0.0, max_tokens=260)'''
assert old_call in s
s = s.replace(old_call, new_call, 1)

io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("patched")
