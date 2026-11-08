import io, os, shutil

P = r"C:\ABRASAX\AGENTS\agents_hub\llm_router.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''    served = out.get("model")
    if requested and served and requested != served and provider == "lmstudio":
        out["requested_model"] = requested
        out["substituted"] = True
    else:
        out["substituted"] = False
    return out
'''

NEW = '''    served = out.get("model")
    if requested and served and _same_model(requested, served):
        out["substituted"] = False
    elif requested and served:
        out["requested_model"] = requested
        out["substituted"] = True
    else:
        out["substituted"] = False
    return out
'''

HELPER = '''def _same_model(requested: str, served: str) -> bool:
    """True when `served` is really the model that was asked for.

    A provider may echo back a full path where the caller sent a bare file name
    (llama.cpp answers model="LFM2.5-1.2B-Instruct-Q6_K.gguf" with the absolute
    .gguf path, and that is NOT a substitution).  Compare normalised tails.
    """
    if requested == served:
        return True

    def norm(s: str) -> str:
        s = str(s).strip().rstrip("/\\\\").replace("\\\\", "/")
        base = s.rsplit("/", 1)[-1]
        return base.lower()

    return norm(requested) == norm(served) and bool(norm(requested))


'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND - refusing to patch")
if "_same_model" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

# Insert the helper immediately before _flag_substitution.
anchor = "def _flag_substitution("
src = src.replace(anchor, HELPER + anchor, 1)

# Correct the now-stale docstring that claims this is LM-Studio-only.
src = src.replace(
    '''    LM Studio substitutes a resident model when asked for a model id it does not
    have, and reports the SUBSTITUTED id in `model`. Callers that must not be
    silently misled (exactness tests, benchmarking, eval harnesses) read
    out["substituted"].''',
    '''    Several providers substitute a resident model when asked for an id they do
    not have, and report the SUBSTITUTED id in `model` (measured 2026-11-01:
    lmstudio AND llamacpp-local both answer a bogus id with HTTP 200 and real
    text). This previously only fired for provider == "lmstudio", so
    llamacpp-local reported substituted=False while serving a different model -
    a false negative that hid a lie. Callers that must not be silently misled
    (exactness tests, benchmarking, eval harnesses) read out["substituted"].''',
    1)

bak = P + ".bak-subfix"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes; backup", bak)
