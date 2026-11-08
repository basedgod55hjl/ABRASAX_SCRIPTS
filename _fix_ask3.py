import io
import ast

p = r"C:\abrasax\tools\abx\ask.py"
s = io.open(p, encoding="utf-8").read()

old = '''    r = Result("abx.ask")
    t0 = time.time()
    plan = _plan(goal, route=route, model=model)'''
new = '''    r = Result("abx.ask")
    t0 = time.time()
    # Bind the proven seat unless the caller named one. A chat-tuned default
    # model talks instead of calling; LOGS/seat.json holds the last model that
    # passed the tool-contract rubric (tools.abx.seat).
    if model is None:
        from .seat import from_disk

        model = from_disk()
    r.add(seat=model)
    plan = _plan(goal, route=route, model=model)'''
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("ask now binds the proven seat")
