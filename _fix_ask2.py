import io
import ast

p = r"C:\abrasax\tools\abx\ask.py"
s = io.open(p, encoding="utf-8").read()

old = """    got = llm.chat(prompt=f"GOAL: {goal}\\n\\nPick the single best tool and reply with the JSON object only.",
                   route=route, model=model, system=PLAN_SYSTEM.format(tools=_tool_contract()),
                   temperature=0.0, max_tokens=200)"""
new = """    # Pass the goal as the *user* turn. Putting it into the system prompt made some
    # routers treat it as a system override; the planner must see a clean contract.
    got = llm.chat(prompt=PLAN_SYSTEM.format(tools=_tool_contract()) + "\\nGOAL: " + goal,
                   route=route, model=model, system=PLAN_SYSTEM.format(tools=_tool_contract()),
                   temperature=0.0, max_tokens=200)"""
assert old in s, "planner call anchor missing"
s = s.replace(old, new, 1)

# a plan is only accepted if the named tool is exact; make the error actionable
s = s.replace(
    'return {"ok": False, "error": f"planner named an unregistered tool {name!r}",',
    'return {"ok": False, "error": f"planner named an unregistered tool {name!r} (contract: {sorted(TOOLS)[:6]}...)",',
)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("patched")
