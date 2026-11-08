"""Prove the substitution regression is real, without pytest internals.

Loads the pre-fix llm_router and checks the behaviour the new tests pin.
The old source is rebuilt by replacing the whole function body between
`def _flag_substitution(` and the next top-level `def `.
"""
import importlib.util, io, os, re, sys, tempfile

REPO = r"C:\ABRASAX"
SRC = os.path.join(REPO, "AGENTS", "agents_hub", "llm_router.py")
text = io.open(SRC, encoding="utf-8").read()
if "_same_model" not in text:
    raise SystemExit("fix not present - nothing to compare against")

OLD_FUNC = '''def _flag_substitution(requested: str | None, out: dict, provider: str) -> dict:
    served = out.get("model")
    if requested and served and requested != served and provider == "lmstudio":
        out["requested_model"] = requested
        out["substituted"] = True
    else:
        out["substituted"] = False
    return out


'''

start = text.index("def _flag_substitution(")
end = text.index("\ndef ", start + 10) + 1
old_src = text[:start] + OLD_FUNC + text[end:]

d = tempfile.mkdtemp(prefix="subproof_")
old_file = os.path.join(d, "old_llm_router.py")
io.open(old_file, "w", encoding="utf-8", newline="\n").write(old_src)

sys.path.insert(0, REPO)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OLD = load(old_file, "old_router")
NEW = load(SRC, "new_router")
assert OLD.__file__ != NEW.__file__, "both loaded from the same file - invalid proof"
print("old module:", OLD.__file__)
print("new module:", NEW.__file__)

GGUF = (r"C:\Users\lucar\.lmstudio\models\lmstudio-community"
        r"\LFM2.5-1.2B-Instruct-GGUF\LFM2.5-1.2B-Instruct-Q6_K.gguf")
BARE = "LFM2.5-1.2B-Instruct-Q6_K.gguf"
BOGUS = "definitely-not-a-model-zzz"

print("\n  %-26s %-15s %-6s %-6s" % ("case", "provider", "old", "new"))
old_false = 0
new_true = 0
for prov in ("llamacpp-local", "lmstudio", "deepseek", "nvidia"):
    o = OLD._flag_substitution(BOGUS, {"model": GGUF}, prov).get("substituted")
    n = NEW._flag_substitution(BOGUS, {"model": GGUF}, prov).get("substituted")
    print("  %-26s %-15s %-6s %-6s" % ("bogus model id", prov, o, n))
    old_false += (o is False)
    new_true += (n is True)

n_inv = NEW._flag_substitution(BARE, {"model": GGUF}, "llamacpp-local").get("substituted")
print("  %-26s %-15s %-6s %-6s" % ("bare filename echo", "llamacpp-local", "-", n_inv))

# The old gate hard-coded provider == "lmstudio", so exactly ONE of the four
# providers (lmstudio) was reported correctly; the other three were false
# negatives. That asymmetry IS the bug.
ok_old = old_false == 3
ok_new = new_true == 4
ok_inv = (n_inv is False)
print()
print("old was correct for only 1 of 4 (lmstudio):", ok_old)
print("new reports True for all 4 providers  :", ok_new)
print("new ignores path echo (no false pos.) :", ok_inv)
print()
if ok_old and ok_new and ok_inv:
    print("PROVEN: the old gate hid substitution; the fix flags it correctly.")
    sys.exit(0)
print("INCONCLUSIVE")
sys.exit(1)
