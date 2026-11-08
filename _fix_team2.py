import io
import ast

# ---- 1. team.py must register the llm + seat tools it drives -------------
p = r"C:\abrasax\tools\abx\team.py"
s = io.open(p, encoding="utf-8").read()
anchor = "from . import stack as _stack  # noqa: F401,E402  registers abx.stack/ports/recover\n"
add = anchor + ("from . import llm as _llm  # noqa: F401,E402  registers abx.llm.*\n"
                "from . import seat as _seat  # noqa: F401,E402  registers abx.seat\n")
assert anchor in s and "from . import llm as _llm" not in s
s = s.replace(anchor, add, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)

# ---- 2. the test asserted a key the SELECT checks intentionally omit -----
t = r"C:\abrasax\tests\test_abx_agents.py"
s = io.open(t, encoding="utf-8").read()
s = s.replace('            assert len(check["allowed"]) >= 4\n',
              '            assert check["expect_tool"] in abx_seat.ALLOWED\n')
io.open(t, "w", encoding="utf-8").write(s)
ast.parse(s)
print("patched team imports + test assertion")
