import io

p = r"C:\abrasax\tools\abx\team.py"
s = io.open(p, encoding="utf-8").read()
anchor = "from .toolcore import TOOLS, Result, tool\n"
add = (
    "from .toolcore import TOOLS, Result, tool\n"
    "# register the tool set this module drives (import side-effects)\n"
    "from . import repo as _repo  # noqa: F401,E402  registers abx.repo.*\n"
    "from . import stack as _stack  # noqa: F401,E402  registers abx.stack/ports/recover\n"
)
assert anchor in s
s = s.replace(anchor, add, 1)
io.open(p, "w", encoding="utf-8").write(s)
import ast
ast.parse(s)
print("ok")
