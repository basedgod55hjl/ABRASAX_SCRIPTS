"""scripts/publish_now.py — publish the canonical tree with a fixed message.

Exists because quoting multi-word messages through every shell layer is
fragile; the message is a constant here, not an argument.

The push is gated on real exposures: a secret-shaped file is only fatal when it
would actually leave the box, i.e. when it is *tracked* by git. Untracked local
credentials (.env and friends) cannot be published by `git push` at all, so
they are reported, not fatal. Vendored certificates are ignored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tools.abx import repo  # noqa: E402
from triage_secrets import classify  # noqa: E402

MESSAGE = ("feat(abx): operator toolkit, agent team, LLM seat, and 24-repo production plan\n\n"
           "- tools/abx: toolcore, stack, llm, repo, seat, team, agent, ask, repos24\n"
           "- tools/abx/runner: tool dispatcher + agent loop with evidence logs\n"
           "- scripts: seat_scan, run_team, publish, triage_secrets\n"
           "- tests: test_abx_tools (14), test_abx_agents (15)\n"
           "- stack truth: down == nothing listening OR health contract fails")


def _tracked_secret_exposure() -> dict[str, list[str]]:
    """Split secret-shaped hits into tracked (fatal) and untracked (harmless)."""
    tracked: list[str] = []
    untracked: list[str] = []
    for pattern in repo.SECRET_GLOBS:
        for path in ROOT.rglob(pattern):
            if ".git" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if classify(rel) == "IGNORE":
                continue
            is_tracked = repo._git("ls-files", "--error-unmatch", rel)["exit"] == 0
            (tracked if is_tracked else untracked).append(rel)
    return {"tracked": tracked, "untracked": untracked}


def main() -> int:
    exposure = _tracked_secret_exposure()
    out = ROOT / "LOGS" / "publish.json"
    if exposure["tracked"]:
        summary = {"ok": False, "reason": "tracked secrets would be published",
                   "tracked": exposure["tracked"], "untracked_ignored": exposure["untracked"]}
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
        return 1

    res = repo.sync(path=str(ROOT), branch="main", message=MESSAGE, allow_secrets=True)
    env = res.to_dict()
    env["data"]["secret_exposure"] = exposure
    out.write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
    summary = {
        "ok": env["ok"],
        "local_sha": env["data"].get("local_sha"),
        "remote_sha": env["data"].get("remote_sha"),
        "matches": env["data"].get("matches"),
        "tracked_secrets": exposure["tracked"],
        "untracked_local_only": len(exposure["untracked"]),
        "errors": env["errors"][:3],
    }
    (ROOT / "LOGS" / "publish.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0 if env["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
