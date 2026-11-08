"""fix_future_imports.py — make ABRASAX-UI's generated dashboards importable.

A generator emitted, in this order: a docstring, a shebang, a SECOND string
literal, then `from __future__ import annotations`. Python requires __future__
imports to be the first statement after the module docstring, so the second
string literal pushes them out of position and the file raises SyntaxError on
import. Nothing else in the file is wrong.

The repair moves the __future__ line to the top of the file. Every other byte is
preserved, including the banner text (which becomes a plain no-op string, but
still readable in source).

    python SCRIPTS/fix_future_imports.py --check
    python SCRIPTS/fix_future_imports.py --go
"""
from __future__ import annotations

import py_compile
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "UI" / "abrasax-ui" / "src"
PATTERN = "from __future__ import"


def broken_files() -> list[Path]:
    out = []
    for f in sorted(SRC.glob("*.py")):
        try:
            py_compile.compile(str(f), cfile=tempfile.mktemp(suffix=".pyc"), doraise=True)
        except py_compile.PyCompileError:
            out.append(f)
    return out


def fix(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8", errors="surrogateescape").splitlines(keepends=True)
    idx = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith(PATTERN)), None)
    if idx is None:
        return {"file": path.name, "ok": False, "why": "no __future__ import found"}
    if idx == 0:
        return {"file": path.name, "ok": False, "why": "already first line"}
    moved = lines.pop(idx)
    lines.insert(0, moved if moved.endswith("\n") else moved + "\n")
    text = "".join(lines)
    path.with_suffix(".py.bak-future").write_text(
        "".join(lines[:idx] + [moved] + lines[idx + 1:]), encoding="utf-8", errors="surrogateescape")
    path.write_text(text, encoding="utf-8", errors="surrogateescape")
    try:
        py_compile.compile(str(path), cfile=tempfile.mktemp(suffix=".pyc"), doraise=True)
        return {"file": path.name, "ok": True, "moved_from_line": idx + 1}
    except py_compile.PyCompileError as exc:
        return {"file": path.name, "ok": False, "why": str(exc).splitlines()[-1][:200]}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    go = "--go" in argv
    targets = broken_files()
    print(f"broken files under {SRC}: {len(targets)}")
    for t in targets:
        print("  " + t.name)
    if not go:
        print("\ndry run: pass --go to repair")
        return 0
    for t in targets:
        res = fix(t)
        print(("  FIXED  " if res["ok"] else "  FAILED ") + str(res))
    remaining = broken_files()
    print(f"\nafter repair, still broken: {[p.name for p in remaining] or 'none'}")
    return 0 if not remaining else 1


if __name__ == "__main__":
    raise SystemExit(main())
