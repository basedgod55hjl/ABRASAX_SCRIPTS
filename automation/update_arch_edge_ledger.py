"""Update DOC/ARCHITECTURE.md edge ledger with re-verified E2/E4/E9 status.

Each replacement is index-anchored on the edge id at the start of the row, so
the file's legacy mojibake arrows do not have to be matched literally.
Idempotent. Backs up first.
"""
import shutil
import sys
from pathlib import Path

DOC = Path("C:/ABRASAX/DOC/ARCHITECTURE.md")
BAK = Path("C:/ABRASAX/DOC/ARCHITECTURE.md.bak-pipeline-e4")

ROWS = {
    "E2": "| E2 | `genesis_seed.bin` \u2192 `unfold` | `unfold.dna_from_bytes()` -> 512 floats | "
          "**yes** *(was: no)* | Closed. `unfold.py:116` maps raw seed bytes to signed-int8/128 "
          "floats in [-1.0, 0.9921875]. Verified: `abrasax unfold` -> `dna_len: 512`, "
          "`seed_sha256 34149faf...`. Regression: `test_enhance_core.py::test_dna_from_bytes_*`. |",

    "E4": "| E4 | `unfold` \u2192 anything | `unfold_manifold()` generator | "
          "**consumer: `hydration.generate_from_seed`** *(was: no consumer)* | "
          "Closed 2026-10-25. hydration carried a *private copy* of the manifold sampler "
          "(`_hash01` + tanh); same seed gave two different manifolds (measured mean |delta| "
          "0.418483, max 0.926594 over 512 cells). Now delegates to "
          "`unfold.manifold_stats`; measured delta is exactly 0.0. "
          "Patch: `SCRIPTS/automation/fix_hydration_unfold_edge.py`. Lock: `test_pipeline_e4.py` (5 tests). |",

    "E9": "| E9 | `ABRASAX-NEO.gguf` \u2192 runtime | `neo_loader.infer()` forward pass | "
          "**yes** *(was: no)* | Closed. Byte tokenizer -> RMSNorm/RoPE/attention/SwiGLU -> "
          "512 logits. Verified: `abrasax neo infer --prompt ABRASAX` -> `ok:true`, "
          "`logits_sha256 f7e56c6e...`, `generated_ids` deterministic; two runs byte-identical "
          "(sha `18CC1B8B...`). Weights are seed-derived: flipping the seed changes the GGUF "
          "hash at identical size. Text is gibberish by design (untrained); the math path is real. |",
}


def main() -> int:
    lines = DOC.read_text(encoding="utf-8", errors="surrogateescape").splitlines(keepends=True)
    changed = []

    for i, line in enumerate(lines):
        for edge, new in ROWS.items():
            if line.startswith(f"| {edge} |") and "pipeline-e4" not in line:
                # only replace if it still carries the stale verdict
                if edge == "E2" and "**no**" not in line:
                    continue
                if edge == "E4" and "no consumer" not in line:
                    continue
                if edge == "E9" and "no such loader" not in line:
                    continue
                lines[i] = new + "\n"
                changed.append(edge)

    if not changed:
        print("no rows needed updating (already applied)")
        return 0

    if not BAK.exists():
        shutil.copy2(DOC, BAK)
        print(f"backup: {BAK}")

    DOC.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
    print(f"updated rows: {sorted(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
