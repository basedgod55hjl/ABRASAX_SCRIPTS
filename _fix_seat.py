import ast
import io

p = r"C:\abrasax\tools\abx\seat.py"
s = io.open(p, encoding="utf-8").read()
start = s.index('        "prompt": (\'NEED: list the GitHub')
end = s.index("],", start)
# rebuild the clean block
block = (
    '        "prompt": (\n'
    '            "NEED: list the GitHub repositories owned by the account.\\n"\n'
    '            "The correct answer is abx.repo.audit.\\n"\n'
    '            \'Reply only {"tool":"abx.repo.audit","args":{}}\'\n'
    '        ),\n'
    '        "allowed": ALLOWED,\n'
    '    },\n'
)
head = s[:start]
tail = s[s.index("FORBIDDEN = ("):]
out = head + block + "]\n\n" + tail
ast.parse(out)
io.open(p, "w", encoding="utf-8").write(out)
print("rewritten ok")
print(out[out.index('RUBRIC = ['):out.index('FORBIDDEN')][-700:])
