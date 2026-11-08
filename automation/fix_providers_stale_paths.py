import io, json, os, shutil

P = r"C:\ABRASAX\CONFIG\llm\providers.json"
raw = io.open(P, encoding="utf-8").read()
d = json.loads(raw)
prov = d.get("providers", d)
lm = prov["llamacpp-local"]["models"]

changed = []

# 1. Stale user in every path: C:\Users\sirch does not exist on this host.
for key, val in list(lm.items()):
    if isinstance(val, str) and "\\Users\\sirch\\" in val:
        lm[key] = val.replace("\\Users\\sirch\\", "\\Users\\lucar\\")
        changed.append("%s -> %s" % (key, lm[key]))

# 2. Record which of those paths actually exist, so the router/config is honest.
status = {}
for key, val in lm.items():
    if isinstance(val, str) and val.lower().endswith(".gguf"):
        status[key] = os.path.exists(val)
prov["llamacpp-local"]["model_path_status"] = status

# 3. The service cannot start at all on this host (stub binary, 0xC0000135).
#    Keep the config, but stop advertising it as a live zero-cost provider.
prov["llamacpp-local"]["notes"] = (
    "Measured 2026-11-01: NOT RUNNABLE on this host. "
    "BUILD/llamacpp/build/bin/llama-server.exe is a 10,752-byte stub that imports "
    "llama-server-impl.dll, which is absent from that directory; it exits "
    "0xC0000135 (STATUS_DLL_NOT_FOUND) in milliseconds, so :8083 never opens. "
    "The LM Studio copies of llama-server.exe are 20KB shims that require "
    "lmstudiocore.dll and abort with a GGML_ASSERT when launched standalone, so "
    "they are not a substitute. The supervisor now blocks this service via a "
    "runnability preflight instead of restarting it forever. Model paths were "
    "also corrected from C:\\Users\\sirch (no such user) to C:\\Users\\lucar."
)

bak = P + ".bak-stalepaths"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(
    json.dumps(d, indent=2, ensure_ascii=False) + "\n")

print("changed paths:")
for c in changed:
    print("  ", c)
print("\nexists:", json.dumps(status))
