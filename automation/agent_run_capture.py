#!/usr/bin/env python
"""agent_run_capture.py — run ONE abrasax agent through the live LLM and persist the record.

Wraps the real CLI (`python -m abrasax run <agent> <task>`), never the library, so the
artifact proves the operator-facing path. Writes:

    LOGS/agent-runs/<UTC-ish local timestamp>-<agent>.json    one full record
    LOGS/agent-runs/index.jsonl                               one summary line per record

Usage
    python SCRIPTS/automation/agent_run_capture.py \
        --agent code-reviewer \
        --task "Review abrasax/brain.py ..." \
        --embed abrasax/brain.py \
        --route lmstudio --model gemma-4-e2b-uncensored-hauhaucs-aggressive --timeout 300

    # directory manifest instead of inlining every file
    ... --agent test-engineer --task "..." --list-dir TESTS/python

Captured per run: agent id, resolved ROLES doctrine (id / file / sha256 / chars), exact argv,
route, requested model, the full task text, embedded-file hashes, wall latency, CLI-reported
duration, stdout content, stderr metadata, model + routed_via as reported by the router, and
token usage *if the CLI emitted it*. The CLI does not: `agents_api.run_live` drops `usage`
(abrasax/agents_api.py:102-115), so `tokens` is null with a note — never invented.

A failed run is a valid record: exit code, stderr tail and error string are stored, verdict
"failed", and the script exits 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "LOGS" / "agent-runs"
INDEX = RUNS_DIR / "index.jsonl"
DEFAULT_PY = ROOT / "PYTHON" / ".venv_gui" / "Scripts" / "python.exe"
SCHEMA = "abrasax.agent-run/1"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------- role doctrine
def role_meta(agent_id: str) -> dict:
    """Resolve the ROLES doctrine the same way agents_api.role_for() does, then hash it."""
    out = {"id": agent_id, "role_id": None, "role_name": None, "role_file": None,
           "role_prompt_chars": 0, "role_prompt_sha256": None, "prompt_loaded": False}
    from abrasax import agents_api  # local import: keeps --help fast and import errors local
    spec = agents_api.role_for(agent_id) or {}
    out["role_id"] = spec.get("id")
    out["role_name"] = spec.get("name")
    out["role_file"] = spec.get("md_path")
    if spec.get("md_path"):
        try:
            text = Path(spec["md_path"]).read_text(encoding="utf-8", errors="replace")
            out["role_prompt_chars"] = len(text)
            out["role_prompt_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            out["prompt_loaded"] = bool(text.strip())
        except OSError as exc:
            out["role_error"] = f"{type(exc).__name__}: {exc}"
    return out


# ---------------------------------------------------------------- prompt building
def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _file_block(path: Path, max_chars: int) -> tuple[str, dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    body = raw[:max_chars]
    meta = {"path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "chars": len(raw), "sha256": _sha(raw),
            "included_chars": len(body), "truncated": len(raw) > len(body)}
    head = (f"\n\n--- FILE {meta['path']} ({meta['chars']} chars, sha256 {meta['sha256'][:16]}) ---\n")
    if meta["truncated"]:
        head += f"[truncated to first {len(body)} chars]\n"
    return head + body, meta


def _dir_block(path: Path, max_files: int) -> tuple[str, dict]:
    rows = []
    for p in sorted(path.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            rows.append(f"  {p.relative_to(path).as_posix():<48} {p.stat().st_size:>7} B")
    body = f"\n\n--- DIRECTORY {path.relative_to(ROOT).as_posix()} ({len(rows)} files) ---\n" + "\n".join(rows[:max_files])
    meta = {"path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "kind": "directory", "files": len(rows), "listed": min(len(rows), max_files)}
    return body, meta


# ---------------------------------------------------------------- CLI invocation
_META_RE = re.compile(r"^\s*\{.*\}\s*$")


def _parse_meta(stderr: str) -> dict:
    """The CLI prints its metadata JSON on stderr after a blank line; take the last JSON object."""
    for line in reversed(stderr.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}") and _META_RE.match(line):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def _last_error_line(stderr: str, rc: int) -> str:
    """Last stderr line that is not the CLI's metadata JSON."""
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    prose = [ln for ln in lines if not (ln.strip().startswith("{") and ln.strip().endswith("}"))]
    if prose:
        return prose[-1].strip()
    return lines[-1].strip() if lines else f"exit {rc}"


def capture(args) -> dict:
    task = args.task
    embedded: list[dict] = []

    for spec in args.embed or []:
        p = Path(spec)
        if not p.is_absolute():
            p = ROOT / p
        if not p.is_file():
            raise SystemExit(f"--embed not a file: {p}")
        block, meta = _file_block(p, args.max_chars)
        task += block
        embedded.append(meta)

    for spec in args.list_dir or []:
        p = Path(spec)
        if not p.is_absolute():
            p = ROOT / p
        if not p.is_dir():
            raise SystemExit(f"--list-dir not a directory: {p}")
        block, meta = _dir_block(p, args.max_listed)
        task += block
        embedded.append(meta)

    py = Path(args.python)
    if not py.is_file():
        raise SystemExit(f"python not found: {py}")

    argv = [str(py), "-m", "abrasax", "run", args.agent, task,
            "--route", args.route, "--timeout", str(args.timeout)]
    if args.model:
        argv += ["--model", args.model]
    if args.no_jev:
        argv.append("--no-jev")

    started = datetime.now().astimezone()
    t0 = time.perf_counter()
    proc = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=args.hard_timeout)
    wall_ms = int((time.perf_counter() - t0) * 1000)
    ended = datetime.now().astimezone()

    stderr = proc.stderr or ""
    meta = _parse_meta(stderr)
    content = (proc.stdout or "").strip()
    ok = proc.returncode == 0
    error = None if ok else _last_error_line(stderr, proc.returncode)

    run_id = f"{started.strftime('%Y%m%dT%H%M%S')}-{args.agent}"
    record = {
        "schema": SCHEMA,
        "run_id": run_id,
        "label": args.label,
        "started_at": started.isoformat(timespec="seconds"),
        "ended_at": ended.isoformat(timespec="seconds"),
        "wall_ms": wall_ms,
        "host": {"python": str(py), "cwd": str(ROOT), "platform": sys.platform},
        "agent": role_meta(args.agent),
        "request": {
            "argv": argv,
            "argv_redacted": [a if len(a) < 400 else f"<task {len(a)} chars>" for a in argv],
            "agent_id": args.agent,
            "route": args.route,
            "model_requested": args.model,
            "timeout_s": args.timeout,
            "jev_gate": not args.no_jev,
            "task_chars": len(task),
            "task": task,
            "embedded": embedded,
        },
        "response": {
            "success": ok,
            "exit_code": proc.returncode,
            "content": content,
            "content_chars": len(content),
            "stderr_meta": meta,
            "stderr_tail": "\n".join(stderr.strip().splitlines()[-8:]) if stderr.strip() else "",
            "error": error,
        },
        "result": {
            "model": meta.get("model"),
            "routed_via": meta.get("routed_via"),
            "provider": meta.get("provider"),
            "cli_duration_ms": meta.get("duration_ms"),
            "tokens": meta.get("usage"),
            "tokens_note": ("CLI did not emit usage; agents_api.run_live drops the router's "
                            "`usage` field (abrasax/agents_api.py:102-115).")
                           if not meta.get("usage") else None,
        },
        "verdict": "ok" if ok else "failed",
        "notes": [],
    }
    if not record["agent"]["prompt_loaded"]:
        record["notes"].append("no ROLES doctrine resolved — agents_api fell back to the generic system prompt")
    return record


def _write(record: dict, runs_dir: Path, index: Path, write_index: bool) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    out = runs_dir / f"{record['run_id']}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if write_index:
        line = {k: record[k] for k in ("schema", "run_id", "label", "started_at", "wall_ms", "verdict")}
        line.update({"agent": record["agent"]["id"], "role_id": record["agent"]["role_id"],
                     "model": record["result"]["model"], "routed_via": record["result"]["routed_via"],
                     "cli_duration_ms": record["result"]["cli_duration_ms"],
                     "content_chars": record["response"]["content_chars"],
                     "file": out.name})
        with index.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return out


def audit_roles(out_path: Path) -> dict:
    """Coverage audit over AGENTS/ROLES: which of the 46 doctrine files are usable prompts."""
    from agents.roles import list_roles, get_role_prompt  # noqa: E402

    rows = []
    for spec in list_roles():
        p = Path(spec["md_path"])
        text = p.read_text(encoding="utf-8", errors="replace")
        body = text
        fm = {}
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                body = parts[2]
                for line in parts[1].splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        fm[k.strip()] = v.strip()
        body_chars = len(body.strip())
        served = get_role_prompt(spec["id"])
        rows.append({
            "id": spec["id"], "name": spec["name"],
            "file": p.name, "bytes": p.stat().st_size,
            "frontmatter_name": fm.get("name"),
            "body_chars": body_chars,
            "served_chars": len(served),
            "served_matches_file": served == text,
            "usable": body_chars >= 80 and bool(fm.get("name")),
        })

    from abrasax import agents_api
    agents = []
    for aid in agents_api.ids():
        spec = agents_api.role_for(aid) or {}
        agents.append({"agent": aid, "role_id": spec.get("id"),
                       "role_name": spec.get("name"),
                       "doctrine": bool(spec.get("md_path")),
                       "md_path": spec.get("md_path")})

    audit = {
        "schema": "abrasax.roles-audit/1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "roles_total": len(rows),
        "roles_usable": sum(1 for r in rows if r["usable"]),
        "roles_unusable": [r for r in rows if not r["usable"]],
        "roles": rows,
        "agents_total": len(agents),
        "agents_with_doctrine": sum(1 for a in agents if a["doctrine"]),
        "agents": agents,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return audit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_run_capture",
                                 description="run one abrasax agent and persist the transcript")
    ap.add_argument("--audit-roles", action="store_true",
                    help="audit AGENTS/ROLES coverage instead of running an agent")
    ap.add_argument("--agent")
    ap.add_argument("--task", default="")
    ap.add_argument("--embed", action="append", metavar="FILE",
                    help="inline a file into the task (repeatable)")
    ap.add_argument("--max-chars", type=int, default=16000,
                    help="per-file inline cap (default 16000)")
    ap.add_argument("--list-dir", action="append", metavar="DIR",
                    help="append a file listing of DIR (repeatable)")
    ap.add_argument("--max-listed", type=int, default=80)
    ap.add_argument("--route", default="lmstudio", choices=["auto", "lmstudio", "nvidia", "xpl"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=300, help="CLI/provider timeout (s)")
    ap.add_argument("--hard-timeout", type=int, default=600, help="subprocess kill (s)")
    ap.add_argument("--no-jev", action="store_true")
    ap.add_argument("--label", default="")
    ap.add_argument("--python", default=str(DEFAULT_PY))
    ap.add_argument("--runs-dir", default=str(RUNS_DIR))
    ap.add_argument("--no-index", action="store_true")
    args = ap.parse_args(argv)

    if args.audit_roles:
        audit = audit_roles(Path(args.runs_dir) / "roles-audit.json")
        print(json.dumps({"roles_total": audit["roles_total"],
                          "roles_usable": audit["roles_usable"],
                          "unusable": [r["file"] for r in audit["roles_unusable"]],
                          "agents_total": audit["agents_total"],
                          "agents_with_doctrine": audit["agents_with_doctrine"],
                          "agents_without": [a["agent"] for a in audit["agents"]
                                             if not a["doctrine"]]}, indent=2))
        return 0

    if not args.agent or not args.task:
        ap.error("--agent and --task are required unless --audit-roles is used")

    try:
        record = capture(args)
    except subprocess.TimeoutExpired as exc:
        started = datetime.now().astimezone()
        record = {
            "schema": SCHEMA,
            "run_id": f"{started.strftime('%Y%m%dT%H%M%S')}-{args.agent}",
            "label": args.label, "started_at": started.isoformat(timespec="seconds"),
            "ended_at": started.isoformat(timespec="seconds"),
            "wall_ms": args.hard_timeout * 1000,
            "host": {"python": args.python, "cwd": str(ROOT), "platform": sys.platform},
            "agent": role_meta(args.agent),
            "request": {"agent_id": args.agent, "route": args.route, "task": args.task,
                        "task_chars": len(args.task), "model_requested": args.model,
                        "timeout_s": args.timeout, "argv": []},
            "response": {"success": False, "exit_code": None, "content": "",
                         "content_chars": 0, "stderr_meta": {},
                         "error": f"TimeoutExpired after {args.hard_timeout}s"},
            "result": {"model": None, "routed_via": None, "provider": None,
                       "cli_duration_ms": None, "tokens": None,
                       "tokens_note": "run did not complete"},
            "verdict": "failed",
            "notes": [f"subprocess killed at --hard-timeout {args.hard_timeout}s"],
        }
        exc = None  # noqa: F841

    out = _write(record, Path(args.runs_dir), Path(args.runs_dir) / "index.jsonl", not args.no_index)
    summary = {"record": str(out), "verdict": record["verdict"],
               "agent": record["agent"]["id"], "role_id": record["agent"]["role_id"],
               "model": record["result"]["model"], "routed_via": record["result"]["routed_via"],
               "wall_ms": record["wall_ms"], "content_chars": record["response"]["content_chars"],
               "error": record["response"]["error"]}
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if record["verdict"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
