"""fix_llamacpp_catalog_claim.py - the catalog called a working binary a stub.

MEASURED 2026-11-01T17:38Z:

    BUILD\\llamacpp\\build\\bin\\llama-server.exe --version
      -> version 0.7.0-dev, built with MSVC 19.44 for Windows AMD64
    llama-server.exe --model MODELS\\gguf\\ABRASAX-NEO.gguf --port 8099
      -> E llama_model_load: unknown model architecture: 'neo'   (exit before bind)

The binary loads its DLLs and parses a GGUF; the earlier note ("10,752-byte stub
whose import llama-server-impl.dll is not beside it") is false - the impl DLL is
in the same folder. What is true is that the only GGUF in the tree declares
`general.architecture = neo`, which stock llama.cpp does not implement, so the
tool (LM Studio's CUDA backend + LFM2.5) remains the launch of record.

The catalog must describe the thing that is, not the theory that was.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\abrasax\services.py")

OLD = '''        # BUILD/llamacpp/build/bin/llama-server.exe is a 10,752-byte stub whose
        # import llama-server-impl.dll is not beside it (exits 0xC0000135 before
        # printing anything), so naming it here described a server that could not
        # start. The working launch is the tool, which uses LM Studio's CUDA
        # backend with the cudart vendor dir on PATH and serves embeddings.'''

NEW = '''        # BUILD/llamacpp/build/bin/llama-server.exe WORKS (measured 2026-11-01:
        # `--version` -> 0.7.0-dev, and it loads the impl DLL and parses a GGUF;
        # the earlier "10 kB stub, DLL missing" note was wrong). It is still not
        # the launch of record: the only GGUF in the tree declares
        # general.architecture = "neo", which stock llama.cpp rejects
        # ("unknown model architecture: 'neo'"), and this row must serve
        # embeddings. The tool pins a real model and passes --embeddings
        # --pooling mean, so ABRASAX_EMBED_URL (:8083) has a 2048-dim contract.'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if NEW in src:
        print("already applied")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor not unique: {src.count(OLD)}")
    TARGET.write_text(src.replace(OLD, NEW, 1), encoding="utf-8", newline="")
    print("patched", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
