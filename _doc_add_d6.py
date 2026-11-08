from pathlib import Path

p = Path(r"C:\abrasax\DOC\RUN-STATE-20261101T1735Z.md")
s = p.read_text(encoding="utf-8")
anchor = "---\n\n## 3. `start all` is now a CLI verb"
assert s.count(anchor) == 1, s.count(anchor)

add = """### D6 - the catalog called a working binary a stub

`services.py` described `BUILD/llamacpp/build/bin/llama-server.exe` as a
"10,752-byte stub whose import llama-server-impl.dll is not beside it".
Measured 2026-11-01T17:38Z:

```
llama-server.exe --version   -> version 0.7.0-dev, built with MSVC 19.44
llama-server.exe --model MODELS\\gguf\\ABRASAX-NEO.gguf --port 8099
  -> E llama_model_load: unknown model architecture: 'neo'    (exit before bind)
```

The binary loads its DLLs and parses a GGUF, so the stub claim was false - an
existing test (`tests/test_supervisor_exe_probe.py`) already said so: the
version goes to stderr and the first probe wrongly read that as broken. The row
still launches the tool, for a different and now-stated reason: the only GGUF in
the tree is an ABRASAX-native artifact, not a llama.cpp architecture.

`SCRIPTS/_probe_neo_gguf.py` reads it without llama.cpp:

```
gguf v3  tensors=21  kv=16
general.architecture  neo     neo.context_length 2048   neo.embedding_length 64
neo.block_count 2             neo.feed_forward_length 256
abrasax.primal_hex    4f5349524953424c58434b
abrasax.seed_sha256   34149faf...
```

So `ABRASAX-NEO.gguf` (790 KB, 2 blocks, 64-dim) is served by
`python -m abrasax neo infer`, not by llama.cpp. The catalog now says exactly
that (`SCRIPTS/fix_llamacpp_catalog_claim.py`).

"""

p.write_text(s.replace(anchor, add + anchor, 1), encoding="utf-8", newline="")
print("doc updated")
