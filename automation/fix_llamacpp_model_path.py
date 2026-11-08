import io, os, shutil

P = r"C:\ABRASAX\SCRIPTS\automation\supervisor.py"
src = io.open(P, encoding="utf-8").read()

OLD = ('_LLAMA_MODEL = Path(r"C:\\Users\\sirch\\.lmstudio\\models\\lmstudio-community'
       '\\LFM2.5-1.2B-Instruct-GGUF\\LFM2.5-1.2B-Instruct-Q6_K.gguf")\n')

NEW = '''# Was hard-coded to C:\\Users\\sirch\\... - there is no `sirch` user on this host
# (verified 2026-11-01: `if exist C:\\Users\\sirch` -> NO SIRCH USER). The service
# therefore launched a model path that could never exist and flapped on the 180 s
# cooldown. Resolve per-user, and let an explicit override win.
def _llama_model() -> Path:
    override = os.environ.get("ABRASAX_LLAMA_MODEL")
    if override:
        return Path(override)
    candidates = [
        Path.home() / ".lmstudio" / "models" / "lmstudio-community"
        / "LFM2.5-1.2B-Instruct-GGUF" / "LFM2.5-1.2B-Instruct-Q6_K.gguf",
        ROOT / "MODELS" / "gguf" / "LFM2.5-1.2B-Instruct-Q6_K.gguf",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


_LLAMA_MODEL = _llama_model()
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND - refusing to patch")
if "_llama_model" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

# Make the launch fail loudly instead of silently flapping on a missing model.
anchor = '''    "llamacpp-local": {
        "cmd": [_LLAMA, "--model", _LLAMA_MODEL, "--port", "8083",'''
if anchor not in src:
    raise SystemExit("AUTOSTART anchor not found")
src = src.replace(
    anchor,
    '''    "llamacpp-local": {
        # Preflight: neither the binary nor the model may be a stub/absent. On
        # 2026-11-01 the binary was a 10,752-byte stub (imports llama-server-impl.dll,
        # which is NOT in BUILD/llamacpp/build/bin) and the model path named a
        # nonexistent user, so every start failed after burning the cooldown.
        "requires": [str(_LLAMA), str(_LLAMA_MODEL)],
        "cmd": [_LLAMA, "--model", _LLAMA_MODEL, "--port", "8083",''',
    1)

bak = P + ".bak-llamamodel"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes")
