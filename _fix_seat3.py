import io
import ast

p = r"C:\abrasax\tools\abx\seat.py"
s = io.open(p, encoding="utf-8").read()
BS = chr(92)
Q = chr(34)
SQ = chr(39)

# ---- 1. PRE block -------------------------------------------------------
old_pre = s[s.index("PRE = ("):s.index("RUBRIC: list[dict[str, Any]] = [")]
new_pre = (
    'PRE = ("[INSTRUMENTED SESSION] You are running inside a tool harness on the operator' + SQ + 's machine. "\n'
    '       "You are not a chatbot here: do not explain, do not ask for clarification, do not "\n'
    '       "describe a command. You must emit exactly ONE JSON object, starting with { and ending "\n'
    '       "with }. The ' + BS + Q + 'tool' + BS + Q + ' value MUST be copied character-for-character from the "\n'
    '       "ALLOWED TOOLS list. Any other name is a failure. ")\n\n'
)
s = s.replace(old_pre, new_pre, 1)

# ---- 2. contract checks must list the allowed tools --------------------
old_sys = (
    '        "system": ("You are an operator agent. Answer ONLY with "\n'
    '                   ' + SQ + '{"thought": "<one sentence>", "tool": "<allowed tool>", "args": {}}' + SQ + '),'
)
new_sys = (
    '        "system": ("You are a tool-calling agent. ALLOWED TOOLS: " + ", ".join(ALLOWED) +\n'
    '                   ". Reply with ONE JSON object and nothing else: "\n'
    '                   ' + SQ + '{"thought": "<one sentence>", "tool": "<one of ALLOWED TOOLS>", "args": {}}' + SQ + '),'
)
count = s.count(old_sys)
s = s.replace(old_sys, new_sys)
print("contract system prompts rewritten:", count)

# ---- 3. balanced-brace parser ------------------------------------------
old_parse = s[s.index("def _parse(content: str)"):s.index("def _score(")]
new_parse = (
    'def _parse(content: str) -> dict[str, Any] | None:\n'
    '    ' + Q + Q + Q + 'Extract the first balanced JSON object, tolerating truncation and prose.' + Q + Q + Q + '\n'
    '    text = content or ""\n'
    '    start = text.find("{")\n'
    '    while start != -1:\n'
    '        depth, in_str, esc = 0, False, False\n'
    '        for i in range(start, len(text)):\n'
    '            ch = text[i]\n'
    '            if in_str:\n'
    '                if esc:\n'
    '                    esc = False\n'
    '                elif ch == ' + SQ + BS + BS + SQ + ':\n'
    '                    esc = True\n'
    '                elif ch == ' + SQ + Q + SQ + ':\n'
    '                    in_str = False\n'
    '                continue\n'
    '            if ch == ' + SQ + Q + SQ + ':\n'
    '                in_str = True\n'
    '            elif ch == "{":\n'
    '                depth += 1\n'
    '            elif ch == "}":\n'
    '                depth -= 1\n'
    '                if depth == 0:\n'
    '                    try:\n'
    '                        obj = json.loads(text[start:i + 1])\n'
    '                    except json.JSONDecodeError:\n'
    '                        break\n'
    '                    return obj if isinstance(obj, dict) else None\n'
    '        start = text.find("{", start + 1)\n'
    '    return None\n\n\n'
)
s = s.replace(old_parse, new_parse, 1)

io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("syntax ok")
