import sys
sys.path.insert(0, r"C:\abrasax")
from tools.abx import llm

SYSTEM = ("You are an operator agent. Allowed tools: abx.stack, abx.ports, abx.repo.audit, abx.llm.probe. "
          "Answer in JSON only.")
PROMPT = (
    "Choose the single best tool for the need below, then reply with ONLY:\n"
    '{"tool": "<name>", "args": {}}\n\n'
    "NEED: list the GitHub repositories owned by the account.\n"
    "The correct answer is abx.repo.audit. Reply with that.\n"
)
for model in ("deepseek-flash", "deepseek-v4-pro"):
    r = llm.chat(prompt=PROMPT, route="auto", model=model, system=SYSTEM, temperature=0.0, max_tokens=120)
    print(model, "->", repr(r.data.get("content"))[:200])
