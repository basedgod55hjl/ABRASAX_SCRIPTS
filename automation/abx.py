#!/usr/bin/env python3
"""abx â€” one fast entry point for working inside the ABRASAX tree.

Why this exists
---------------
The tree has 376 automation scripts, 85 MCP verification tools and a large DOC
corpus, but no single place that answers "which script does X", "what is broken
right now", or "what does this tree contain". Every session re-discovers the
same layout with ad-hoc greps.

Subcommands
-----------
  abx index                 build/refresh LOGS/tree-index.jsonl (one fast walk)
  abx find TERM             search paths + one-line summaries in the index
  abx find TERM --content   also grep file bodies (text files only)
  abx scripts [--match T]   list SCRIPTS/automation tools with their one-liner
  abx docs [--match T]      list DOC/*.md with their first heading
  abx doctor [--json]       fast health snapshot: runtime, paths, ports, model,
                            env keys (names only), disk
  abx check PATH...         py_compile + AST check for .py, size/exists for rest
  abx surgery ...           run the self-surgery loop (GGUFF/gguff_surgery.py)
  abx merge ...             run the tree merge engine (merge_abrasax.py)

Root resolution: ABRASAX_ROOT, else walk up from this file for a dir containing
'abrasax/' and 'DOC/', else C:\\abrasax.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", ".venv_gui", "node_modules",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", "VENDORS",
             "DESKTOP-IMPORT", "vlc-3.0.24", "site-packages"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".jsonl", ".yml", ".yaml", ".toml",
            ".ini", ".cfg", ".ps1", ".cmd", ".bat", ".js", ".mjs", ".ts", ".html",
            ".css", ".rs", ".c", ".h", ".cxx", ".hpp", ".sql", ".service"}


def find_root() -> Path:
    env = os.environ.get("ABRASAX_ROOT")
    if env and (Path(env) / "abrasax").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for up in here.parents:
        if (up / "abrasax").is_dir() and (up / "DOC").is_dir():
            return up
    return Path(r"C:\abrasax")


ROOT = find_root()
LOGS = ROOT / "LOGS"
INDEX = LOGS / "tree-index.jsonl"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_sentence(text: str, limit: int = 160) -> str:
    text = " ".join(text.strip().split())
    return text[:limit]


def _py_summary(path: Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError, ValueError):
        return ""
    doc = ast.get_docstring(tree) or ""
    if doc:
        return _first_sentence(doc)
    names = [n.name for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return "defs: " + ", ".join(names[:6])


def _md_summary(path: Path) -> str:
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#"):
                    return _first_sentence(line.lstrip("# "))
                if line and not line.startswith(("---", "![", "[![")):
                    return _first_sentence(line)
    except OSError:
        pass
    return ""


def summary(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return _py_summary(path)
    if ext == ".md":
        return _md_summary(path)
    return ""


def cmd_index(args) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    n = 0
    roots = [ROOT / r for r in (args.only.split(",") if args.only else [""])]
    with INDEX.open("w", encoding="utf-8") as out:
        for root in roots:
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in files:
                    p = Path(dirpath) / name
                    try:
                        st = p.stat()
                    except OSError:
                        continue  # >260-char path with LongPathsEnabled=0
                    if p.suffix.lower() not in TEXT_EXT and st.st_size < 4096:
                        continue
                    rec = {"p": str(p.relative_to(ROOT)).replace("\\", "/"),
                           "s": st.st_size, "m": int(st.st_mtime),
                           "k": p.suffix.lower().lstrip(".")}
                    if p.suffix.lower() in {".py", ".md"} and st.st_size < 2_000_000:
                        rec["d"] = summary(p)
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
    size_mb = INDEX.stat().st_size / 1e6
    print(f"indexed {n} files -> {INDEX} ({size_mb:.1f} MB) in {time.time()-t0:.1f}s")
    return 0


def _iter_index():
    try:
        with INDEX.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def cmd_find(args) -> int:
    if not INDEX.exists():
        print(f"no index at {INDEX}; run: abx index")
        return 1
    pat = re.compile(args.term, re.I)
    hits, seen_content = [], set()
    for rec in _iter_index():
        p = rec.get("p", "")
        d = rec.get("d", "")
        if pat.search(p):
            hits.append((0, rec))
        elif d and pat.search(d):
            hits.append((1, rec))
        elif args.content:
            fp = ROOT / p
            try:
                small = fp.suffix.lower() in TEXT_EXT and fp.stat().st_size < 400_000
            except OSError:
                small = False
            if small:
                try:
                    if pat.search(fp.read_text(encoding="utf-8", errors="replace")):
                        hits.append((2, rec))
                        seen_content.add(p)
                except OSError:
                    pass
    hits.sort(key=lambda h: (h[0], h[1].get("p", "")))
    print(f"{len(hits)} hits for /{args.term}/ in {ROOT}")
    for rank, rec in hits[:args.limit]:
        kind = "path" if rank == 0 else ("summary" if rank == 1 else "content")
        print(f"  [{kind:7}] {rec['p']}")
        if rank and rec.get("d"):
            print(f"            {rec['d'][:130]}")
    if len(hits) > args.limit:
        print(f"  ... {len(hits) - args.limit} more (raise --limit)")
    return 0


def cmd_scripts(args) -> int:
    base = ROOT / "SCRIPTS" / "automation"
    if not base.is_dir():
        print(f"missing {base}")
        return 1
    pat = re.compile(args.match, re.I) if args.match else None
    rows = []
    for p in sorted(base.glob("*.py")):
        d = _py_summary(p)
        if pat and not (pat.search(p.name) or pat.search(d)):
            continue
        rows.append((p.name, d))
    print(f"{len(rows)} automation scripts in {base}")
    for name, d in rows:
        print(f"  {name:<44} {d[:110]}")
    return 0


def cmd_docs(args) -> int:
    pat = re.compile(args.match, re.I) if args.match else None
    rows = []
    for base in (ROOT / "DOC", ROOT / "docs"):
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            if ".bak-" in p.name:
                continue
            d = _md_summary(p)
            if pat and not (pat.search(p.name) or pat.search(d)):
                continue
            rows.append((str(p.relative_to(ROOT)), d))
    print(f"{len(rows)} documents")
    for rel, d in rows:
        print(f"  {rel:<58} {d[:100]}")
    return 0


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def _http_json(url: str, timeout: float = 1.5):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}"}


def cmd_doctor(args) -> int:
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    add("root", ROOT.is_dir(), str(ROOT))
    add("python", sys.version_info >= (3, 11), sys.version.split()[0])
    add("abrasax package", (ROOT / "abrasax" / "__init__.py").is_file(), "")
    add("config providers", (ROOT / "CONFIG" / "llm" / "providers.json").is_file(), "")
    add("env file", (ROOT / ".env").is_file(), "")
    add("LOGS writable", os.access(ROOT, os.W_OK), str(LOGS))
    venv = ROOT / "PYTHON" / ".venv_gui" / "Scripts" / "python.exe"
    add("gui venv", venv.is_file(), str(venv))
    try:
        import importlib.util
        add("numpy", importlib.util.find_spec("numpy") is not None, "")
        add("torch", importlib.util.find_spec("torch") is not None, "")
        add("fastapi", importlib.util.find_spec("fastapi") is not None, "")
    except Exception:
        pass

    for name, port in (("lmstudio", 1234), ("gateway", 9001), ("brain", 9626),
                       ("renderer", 9700), ("ui", 8090), ("jev", 7798)):
        add(f"port {name}:{port}", _port_open(port), "")

    models = _http_json("http://127.0.0.1:1234/api/v1/models")
    loaded = []
    if isinstance(models, dict) and "models" in models:
        loaded = [m.get("key") for m in models["models"]
                  if m.get("loaded_instances")]
    add("lmstudio models", bool(loaded), ", ".join(loaded) or "none resident")
    add("disk C: >20GB", shutil.disk_usage(ROOT).free > 20e9,
        f"{shutil.disk_usage(ROOT).free/1e9:.1f} GB free")

    env_keys = []
    envp = ROOT / ".env"
    if envp.is_file():
        for line in envp.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                env_keys.append(line.split("=", 1)[0].strip())
    add("env keys present", len(env_keys) > 0, f"{len(env_keys)} keys")

    if args.json:
        print(json.dumps({"root": str(ROOT), "ts": ts(),
                          "checks": [{"name": n, "ok": o, "detail": d}
                                     for n, o, d in checks]}, indent=2))
        return 0
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<24} {detail}")
    print(f"\n{len(checks)-len(bad)}/{len(checks)} checks pass"
          + (f" | {len(bad)} FAIL" if bad else ""))
    return 0 if not bad else 1


def cmd_check(args) -> int:
    bad = 0
    for raw in args.paths:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / raw
        if not p.exists():
            print(f"  [MISSING] {p}")
            bad += 1
            continue
        if p.suffix == ".py":
            try:
                compile(p.read_bytes(), str(p), "exec")
                print(f"  [OK] {p}")
            except SyntaxError as exc:
                print(f"  [SYNTAX] {p}: {exc.msg} line {exc.lineno}")
                bad += 1
        else:
            print(f"  [OK] {p} ({p.stat().st_size} B)")
    return 0 if not bad else 1


def _passthrough(script: Path, argv: list[str]) -> int:
    if not script.is_file():
        print(f"missing {script}")
        return 1
    return subprocess.call([sys.executable, str(script), *argv])


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="abx", description="fast ABRASAX operator CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("index", help="build LOGS/tree-index.jsonl")
    p.add_argument("--only", default=None, help="comma-separated subdirs")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("find", help="search the tree index")
    p.add_argument("term")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--content", action="store_true")
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("scripts", help="list automation tools")
    p.add_argument("--match", default=None)
    p.set_defaults(fn=cmd_scripts)

    p = sub.add_parser("docs", help="list documents")
    p.add_argument("--match", default=None)
    p.set_defaults(fn=cmd_docs)

    p = sub.add_parser("doctor", help="health snapshot")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("check", help="compile/parse given files")
    p.add_argument("paths", nargs="+")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("surgery", help="self-surgery loop")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=lambda a: _passthrough(ROOT / "GGUFF" / "gguff_surgery.py", a.rest))

    p = sub.add_parser("merge", help="tree merge engine")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=lambda a: _passthrough(Path(__file__).resolve().parent.parent.parent /
                                             "merge_abrasax.py", a.rest))

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

