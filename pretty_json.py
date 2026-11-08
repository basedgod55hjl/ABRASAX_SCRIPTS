"""pretty_json.py — make minified JSON greppable without altering the originals.

findstr dies on any line over ~8191 chars, and one 2.4 MB single-line JSON kills
whole searches. Rewriting the operator's files in place would be a side effect they
did not ask for, so this writes `<name>.pretty.json` next to each original and
leaves the original byte-identical.

Each conversion is proved lossless first: parse, re-serialise, parse again, and
compare the parsed structures. If the round-trip is not equal, nothing is written.

    python SCRIPTS/pretty_json.py --report
    python SCRIPTS/pretty_json.py --go
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HOME = Path(r"C:\Users\lucar")
CANDIDATES = ["_urel.json", "jev_openapi.json", "nv1.json", "nv2.json"]

LIMIT = 3000  # chars per line; anything wider is unusable with findstr


def longest_line(p: Path) -> int:
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            return max((len(ln) for ln in fh), default=0)
    except OSError:
        return -1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    go = "--go" in argv
    print(f"{'file':<22} {'orig chars/line':>16}  {'status'}")
    for name in CANDIDATES:
        src = HOME / name
        if not src.exists():
            print(f"{name:<22} {'absent':>16}")
            continue
        wide = longest_line(src)
        try:
            original = json.loads(src.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            print(f"{name:<22} {wide:>16}  NOT JSON ({exc.msg})")
            continue
        pretty = json.dumps(original, indent=2, ensure_ascii=False)
        # prove the round-trip before writing anything
        if json.loads(pretty) != original:
            print(f"{name:<22} {wide:>16}  ROUND-TRIP MISMATCH - skipped")
            continue
        dst = src.with_suffix(".pretty.json")
        narrowed = max((len(ln) for ln in pretty.splitlines()), default=0)
        status = "would write" if not go else "written"
        if go:
            dst.write_text(pretty, encoding="utf-8")
            status = f"written ({dst.stat().st_size/1e6:.1f} MB)"
        print(f"{name:<22} {wide:>16}  {status}; widest line -> {narrowed}")
    print("\noriginals untouched" + ("" if go else "; pass --go to write the .pretty copies"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
