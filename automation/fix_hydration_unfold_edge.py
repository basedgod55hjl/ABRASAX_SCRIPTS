"""Make abrasax.hydration sample the manifold through abrasax.unfold.

Defect closed: generate_from_seed() re-implemented the manifold sampler inline
(_hash01 + tanh) instead of calling unfold.unfold_row(). Same seed, two
different manifolds -- measured mean |delta| 0.418, max 0.927 over 512 cells.
ARCHITECTURE.md SS1.2 E4 verdict "no consumer" is correct until this is fixed.

Idempotent. Backs up first.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path("C:/ABRASAX/abrasax/hydration.py")
BAK = TARGET.with_suffix(".py.bak-pipeline-e4")

OLD = '''    mean = 0.0
    sq = 0.0
    n = 0
    for t in range(sample):
        for d in range(sample):
            v = 0.5 + 0.4634 * math.tanh(
                ((_hash01(seed_hash, t, d) - 0.5) * 12.0) * math.cos(PHI * t / max(sample, 1))
            )
            mean += v
            sq += v * v
            n += 1
    mean /= n
    std = math.sqrt(max(sq / n - mean * mean, 0.0))
'''

NEW = '''    # Sample the manifold through the single canonical sampler in `unfold`.
    # This is edge E4: before this, hydration carried a private copy of the
    # PRNG and the two producers disagreed (mean |delta| 0.418 over 512 cells).
    from . import unfold as _unfold

    _dna = _unfold.dna_from_bytes(seed, dims=512)
    _ustats = _unfold.manifold_stats(_dna, vocab=sample, dim=sample)
    mean = _ustats["mean"]
    std = _ustats["std"]
    n = _ustats["n"]
'''

MANIFEST_OLD = '''        "manifold_stats": {"mean": round(mean, 4), "std": round(std, 4), "sampled": n},'''

MANIFEST_NEW = '''        "manifold_stats": {"mean": round(mean, 4), "std": round(std, 4), "sampled": n},
        "manifold_source": "abrasax.unfold.manifold_stats",'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")

    if "abrasax.unfold.manifold_stats" in src:
        print("already applied - no change")
        return 0

    if OLD not in src:
        print("FAIL: anchor block not found verbatim; refusing to patch blind")
        return 1

    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
        print(f"backup: {BAK}")

    patched = src.replace(OLD, NEW, 1)

    if MANIFEST_OLD in patched:
        patched = patched.replace(MANIFEST_OLD, MANIFEST_NEW, 1)
    else:
        print("FAIL: manifest anchor not found")
        return 1

    compile(patched, str(TARGET), "exec")  # syntax gate before writing
    TARGET.write_text(patched, encoding="utf-8")
    print(f"patched: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
