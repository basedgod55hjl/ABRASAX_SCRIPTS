"""Wire ABRASAX-NEO into the gateway as an opt-in, non-auto provider.

Why opt-in and NOT in policy.order: NEO's weights are an untrained SHA-256
stream, so its text is gibberish by design (see neo_loader's own disclaimer).
Putting it anywhere in the auto fallback chain would silently serve noise to
production traffic. Explicit `model: "neo:..."` is the only way to reach it.

Idempotent. Backs up first.
"""
import json
import shutil
import sys
from pathlib import Path

CFG = Path("C:/ABRASAX/CONFIG/llm/providers.json")
BAK = CFG.with_suffix(".json.bak-neo-provider")

NEO = {
    "type": "native",
    "adapter": "abrasax.neo_loader",
    "models": {
        "default": "ABRASAX-NEO",
        "path": "C:/ABRASAX/MODELS/gguf/ABRASAX-NEO.gguf",
    },
    "notes": "Genesis artifact, not a trained model: 21 tensors, weights are a "
             "deterministic SHA-256 -> Box-Muller -> K/PHI stream. Text quality is "
             "meaningless; the forward pass is real (byte tokenizer -> RMSNorm/RoPE/"
             "attention/SwiGLU -> 512 logits, ~44 tok/s numpy). NEVER add to "
             "policy.order -- reach it only by explicit model 'neo:<prompt>'.",
}


def main() -> int:
    raw = CFG.read_text(encoding="utf-8")
    data = json.loads(raw)

    if "neo" in data.get("providers", {}):
        print("already present - no change")
        return 0

    if not BAK.exists():
        shutil.copy2(CFG, BAK)
        print(f"backup: {BAK}")

    data["providers"]["neo"] = NEO
    data["updated"] = "2026-10-25"

    # hard guard: neo must never be in the auto chain
    assert "neo" not in data["policy"]["order"], "neo must not be auto-routable"

    CFG.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    # prove it round-trips
    back = json.loads(CFG.read_text(encoding="utf-8"))
    assert back["providers"]["neo"]["adapter"] == "abrasax.neo_loader"
    assert "neo" not in back["policy"]["order"]
    print("patched: neo registered as opt-in provider (not in policy.order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
