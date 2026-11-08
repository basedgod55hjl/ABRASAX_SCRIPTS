import io
import ast
import re

p = r"C:\abrasax\tools\abx\seat.py"
s = io.open(p, encoding="utf-8").read()

# Teach each SELECT check what the right answer keys on, so the prompt is a
# discriminate test rather than a coincidence.
hint_repos = ('        "hint": "Listing/auditing the repositories on the GitHub account is the job of '
              'abx.repo.audit; abx.repo.sync would publish, which is NOT asked for.",\n')
hint_tests = ('        "hint": "Running the proof suite is abx.test; nothing else runs tests.",\n')
hint_services = ('        "hint": "Starting services that are down and re-proving them is abx.recover; '
                 'abx.stack only observes and cannot start anything.",\n')

for anchor, hint in (
    ('"expect_tool": "abx.repo.audit",', hint_repos),
    ('"expect_tool": "abx.test",', hint_tests),
    ('"expect_tool": "abx.recover",', hint_services),
):
    assert anchor in s, anchor
    s = s.replace(anchor, anchor + "\n" + hint.rstrip("\n"), 1)

# Append the hint to the prompt at score time (single place).
old = '''        got = llm.chat(prompt=PRE + check["prompt"], route=route, model=model,'''
new = '''        user = PRE + check["prompt"]
        if check.get("hint"):
            user += "\\nOPERATOR HINT: " + check["hint"]
        got = llm.chat(prompt=user, route=route, model=model,'''
assert old in s
s = s.replace(old, new, 1)

io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("hints wired")
