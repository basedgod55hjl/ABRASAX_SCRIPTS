"""fix_lmstudio_default_model.py - the configured default cannot fit on this GPU.

MEASURED 2026-11-01T18:29Z:

    POST :1234/v1/chat/completions  model=gemma-4-e2b-uncensored-hauhaucs-aggressive
    -> HTTP 500 <html>Internal Server Error</html>

while `liquid/lfm2.5-1.2b` answers (36 tokens, twice today) and the same
llama-server process serves :8083 at ~130 tok/s.

The reason is arithmetic, not config taste: the GTX 1660 Ti has 6 GB, llama.cpp
already holds ~1.4 GB for :8083, and gemma-4-e2b is a 4.0 GB file - measured free
VRAM during this session: 444-555 MB. LM Studio cannot load it, so every request
that names the default model fails, and `route="auto"` then falls through to
llamacpp-local. Local-first still held (zero paid calls), but the *first* local
provider was a dead end on every request.

providers.json now names the model that is actually resident, for every chat
alias. The embedding alias keeps its embedder. If the operator later frees VRAM
(or swaps the card), gemma can be restored by editing one file - and the note
that says why is left in the config.

Idempotent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CFG = Path(r"C:\abrasax\CONFIG\llm\providers.json")
CHAT = "liquid/lfm2.5-1.2b"


def main() -> int:
    data = json.loads(CFG.read_text(encoding="utf-8-sig"))
    prov = data["providers"]["lmstudio"]
    models = prov.setdefault("models", {})
    changed = {}
    for alias, value in list(models.items()):
        if alias == "embed":
            continue
        if value != CHAT:
            changed[alias] = (value, CHAT)
            models[alias] = CHAT
    prov["notes"] = dict(prov.get("notes") or {})
    prov["notes"]["vram"] = (
        "2026-11-01: default chat model is liquid/lfm2.5-1.2b because "
        "gemma-4-e2b (4.0 GB) returned HTTP 500 on a 6 GB card that already "
        "gives ~1.4 GB to llama.cpp :8083 (measured free VRAM 444-555 MB). "
        "Restore gemma only when the VRAM budget exists."
    )
    data["policy"]["notes"] = (data["policy"].get("notes", "") +
                               " | lmstudio default retargeted to the resident "
                               "LFM2.5 (gemma-4-e2b cannot fit alongside :8083).")
    CFG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="")
    print("chat aliases changed:", len(changed))
    for k, (old, new) in changed.items():
        print(f"  {k}: {old} -> {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
