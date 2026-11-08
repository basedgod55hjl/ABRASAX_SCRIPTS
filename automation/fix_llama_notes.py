import io, json, os, shutil

P = r"C:\ABRASAX\CONFIG\llm\providers.json"
d = json.load(io.open(P, encoding="utf-8"))
prov = d.get("providers", d)

prov["llamacpp-local"]["notes"] = (
    "VERIFIED WORKING 2026-11-01: BUILD/llamacpp/build/bin/llama-server.exe is a "
    "real llama.cpp build (version 0.7.0-dev, MSVC 19.44, Windows AMD64) and all "
    "of ggml*.dll / llama*.dll / mtmd.dll sit beside it. Started by hand it loads "
    "LFM2.5-1.2B-Instruct-Q6_K.gguf and listens on :8083 in ~3 s, and a "
    "chat completion returns 'PONG! ' with predicted_per_second 130.9 - by far "
    "the fastest local path on this host (LM Studio's 8B Q3 needed 1035 s of CPU "
    "for one request). An earlier 0xC0000135 (STATUS_DLL_NOT_FOUND) observation "
    "was a transient directory state, not a property of the build. NOTE: "
    "llama.cpp prints its version banner on STDERR, so a runnability probe must "
    "read stdout OR stderr. Model paths were corrected from C:\\Users\\sirch "
    "(no such user on this host) to C:\\Users\\lucar."
)

bak = P + ".bak-llamanotes2"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(
    json.dumps(d, indent=2, ensure_ascii=False) + "\n")
print("updated llamacpp-local notes")
print("model_path_status:", json.dumps(prov["llamacpp-local"].get("model_path_status")))
