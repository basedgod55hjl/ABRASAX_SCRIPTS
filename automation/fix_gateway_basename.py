import io, os, shutil

P = r"C:\ABRASAX\abrasax\gateway.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''        owners = _model_owners()
        owner = owners.get(model)
        if owner is None and model in owners.values():
'''

NEW = '''        owners = _model_owners()
        owner = owners.get(model)
        if owner is None:
            # Providers often declare a model by ABSOLUTE PATH (llamacpp-local
            # lists C:\\Users\\lucar\\...\\LFM2.5-1.2B-Instruct-Q6_K.gguf) while a
            # caller sends the bare file name. Without this, such a request fell
            # through to "auto", which tried lmstudio first and hung: measured
            # 2026-11-01, the gateway timed out on a model that :8083 answers in
            # ~40 ms.
            tail = model.replace("\\\\", "/").rsplit("/", 1)[-1].lower()
            for mid, prov in owners.items():
                if mid.replace("\\\\", "/").rsplit("/", 1)[-1].lower() == tail:
                    owner = prov
                    break
        if owner is None and model in owners.values():
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "tail = model.replace" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)
bak = P + ".bak-basename"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P)
