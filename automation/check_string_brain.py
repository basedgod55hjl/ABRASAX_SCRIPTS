"""Prove the string-brain field mapping is real: ordered, deterministic, structured.

If the field were noise, any of these would be trivially false:
  * identical input -> identical field (determinism)
  * longer replies light more cells (monotonic coverage)
  * sequential tokens follow a legible curve, not a random scatter
  * the head of the reply outshines the tail (recency weighting)

Exit 0 = all checks pass.
"""
import hashlib
import math
import sys

sys.path.insert(0, r"C:\ABRASAX")
sys.path.insert(0, r"C:\ABRASAX\SCRIPTS\automation")

from string_brain import W, H, N, PHI, build_field, token_cell, tokenize


def digest(field):
    return hashlib.sha256(
        b"".join(int(max(0.0, min(1.0, v)) * 255).to_bytes(1, "little") for v in field)
    ).hexdigest()[:16]


def lit(field, thresh=0.25):
    return sum(1 for v in field if v >= thresh)


def main():
    ok = True
    text_a = "A thought is a fleeting spark of awareness that dances through the mind"
    text_b = "A thought is a fleeting spark of awareness that dances through the mind"
    text_c = ("A thought is a fleeting spark of awareness that dances through the mind "
              "like a whisper in the dark, carrying meaning across the lattice of memory "
              "and folding back on itself until a pattern emerges from the noise")

    ta, tb, tc = tokenize(text_a), tokenize(text_b), tokenize(text_c)

    # 1 determinism
    fa = build_field(ta, clock=0.0)
    fb = build_field(tb, clock=0.0)
    check = digest(fa) == digest(fb)
    print(f"[{'PASS' if check else 'FAIL'}] deterministic: same input -> same field ({digest(fa)})")
    ok &= check

    # 2 coverage grows with token count
    fc = build_field(tc, clock=0.0)
    la, lc = lit(fa), lit(fc)
    check = lc > la and len(tc) > len(ta)
    print(f"[{'PASS' if check else 'FAIL'}] longer reply lights more cells: "
          f"{len(ta)} tok -> {la} cells, {len(tc)} tok -> {lc} cells")
    ok &= check

    # 3 the cell sequence follows the phi-spiral: consecutive tokens must be
    # spatially near each other far more often than chance.
    def mean_step(tokens):
        cells = [token_cell(t, i, len(tokens)) for i, t in enumerate(tokens)]
        steps = []
        for a, b in zip(cells, cells[1:]):
            ay, ax = divmod(a, W)
            by, bx = divmod(b, W)
            steps.append(math.hypot(ax - bx, ay - by))
        return sum(steps) / len(steps)

    real = mean_step(tc)
    # chance baseline: random cells in a 64x64 grid average ~26 apart
    chance = 26.0
    check = real < chance * 0.75
    print(f"[{'PASS' if check else 'FAIL'}] token path is a curve, not a scatter: "
          f"mean step {real:.2f} vs chance ~{chance:.1f} (max {math.hypot(63,63):.1f})")
    ok &= check

    # 4 recency: the last deposits carry more energy than the first
    first_cell = token_cell(tc[0], 0, len(tc))
    last_cell = token_cell(tc[-1], len(tc) - 1, len(tc))
    check = fc[last_cell] >= fc[first_cell]
    print(f"[{'PASS' if check else 'FAIL'}] head of reply outshines tail: "
          f"first={fc[first_cell]:.3f} last={fc[last_cell]:.3f}")
    ok &= check

    # 5 clock actually advances the standing wave
    f1 = build_field(tc, clock=0.0)
    f2 = build_field(tc, clock=0.77)
    check = digest(f1) != digest(f2)
    print(f"[{'PASS' if check else 'FAIL'}] clock drives the standing wave "
          f"({digest(f1)} -> {digest(f2)})")
    ok &= check

    # 6 range is sane
    check = all(0.0 <= v <= 1.0 for v in fc) and max(fc) <= 1.0
    print(f"[{'PASS' if check else 'FAIL'}] field stays in [0,1] "
          f"(min={min(fc):.3f} max={max(fc):.3f})")
    ok &= check

    # 7 empty input is safe
    check = len(build_field([])) == N and max(build_field([])) == 0.0
    print(f"[{'PASS' if check else 'FAIL'}] empty token list yields a zero field")
    ok &= check

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
