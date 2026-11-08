import io
import ast

p = r"C:\abrasax\tools\abx\llm.py"
s = io.open(p, encoding="utf-8").read()

old = '''    t0 = time.time()
    try:
        out = hub.llm_chat(prompt, **kwargs)'''
new = '''    # The router accepts either a bare string or an OpenAI messages list. The
    # messages form is the only one that reliably carries a tool contract, so
    # build it here and fall back to the bare string on older routers.
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    t0 = time.time()
    try:
        out = hub.llm_chat(messages if len(messages) > 1 else prompt, **kwargs)'''
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("patched llm.chat to send proper messages")
