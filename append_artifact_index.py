"""append_artifact_index.py — a handover index for everything created today.

Twenty-odd scripts and a dozen logs appeared under SCRIPTS/ and LOGS/ during this
session. Without an index, the next person sees a pile and cannot tell the
verifiers from the one-shot patches. This lists each by purpose.

    python SCRIPTS/append_artifact_index.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "DOC" / "SESSION-STATE-20261101.md"
MARK = "## 7. Artifacts created this session"

VERIFIERS = [
    ("SCRIPTS/check_rebuilt.py", "reads the account back independently of the build tool"),
    ("SCRIPTS/verify_restored.py", "restored repo tree hash == mirror tree hash"),
    ("SCRIPTS/verify_pushed_tree.py", "every path on GitHub == local staged HEAD"),
    ("SCRIPTS/verify_rebuild_identity.py", "visibility / branch / description drift == 0"),
    ("SCRIPTS/verify_ci_landed.py", "remote ci.yml == template, byte for byte"),
    ("SCRIPTS/check_attribution.py", "every commit resolves to the account"),
    ("SCRIPTS/check_leak_status.py", "authoritative read of the orphaned commit"),
    ("SCRIPTS/verify_leak_content.py", "does the leak hold the LIVE token (booleans only)"),
    ("SCRIPTS/scan_mirrors_for_pat.py", "sweeps every object of every mirror for the token"),
    ("SCRIPTS/local_ci.py", "runs CI's compile step against the staged trees"),
    ("SCRIPTS/gate.sh", "the gate itself, extracted so it can be tested"),
    ("SCRIPTS/gate_test.sh", "proves the gate fails on a broken file and passes on a clean tree"),
    ("SCRIPTS/check_ci.py", "workflow presence + latest run per rebuilt repo"),
    ("SCRIPTS/ci_diagnose.py", "failing step names for a run"),
    ("SCRIPTS/ci_annotations.py", "failure message without needing log access"),
    ("SCRIPTS/ci_billing_timeline.py", "when Actions stopped working, across all repos"),
    ("SCRIPTS/check_identity.py", "account record behind the token"),
    ("SCRIPTS/check_email.py", "is the commit email a verified account address"),
]

ACTORS = [
    ("SCRIPTS/snapshot_repo_meta.py", "full API record per repo before anything destructive"),
    ("SCRIPTS/rebuild_repos.py", "gate -> delete -> create -> publish -> prove (resumable)"),
    ("SCRIPTS/rebuild_until_unblocked.py", "waits out GitHub's creation block, then finishes"),
    ("SCRIPTS/rebuild_retry.py", "rounds-based retry supervisor"),
    ("SCRIPTS/apply_ci_template.py", "installs the real gate into every source tree"),
    ("SCRIPTS/fix_future_imports.py", "repairs the __future__ position that broke 3 files"),
    ("SCRIPTS/dedupe_i.py", "hash-proven duplicate removal on I:"),
    ("SCRIPTS/reclaim_c.py", "stage prune + home scratch, both gated"),
    ("SCRIPTS/recycle_bins.ps1", "sizes every volume's $Recycle.Bin"),
    ("SCRIPTS/patch_*.py / patch_*.mjs", "one-shot, self-documenting fixes (each keeps a .bak)"),
]

LOGS = [
    ("LOGS/rebuild_2026*.json", "every publish attempt, per repo"),
    ("LOGS/rebuild_unblock.jsonl", "the wait for GitHub's rate limit to lift"),
    ("LOGS/pushed_tree.json", "path-level content equality"),
    ("LOGS/local_ci.json", "per-tree compile results"),
    ("LOGS/ci_status.json", "workflow + latest run per repo"),
    ("LOGS/ci_timeline.json", "newest success / newest run per repo"),
    ("LOGS/pat_scan.json", "token-bearing blob SHAs per mirror"),
    ("LOGS/dedupe_I.json", "every deletion decision with both hashes"),
    ("LOGS/reclaim_c.json", "what was removed and why it was safe"),
    ("LOGS/repo_full_20261101T090922Z.json", "pre-delete snapshot (identity source of truth)"),
]


def table(title: str, rows: list[tuple[str, str]]) -> str:
    out = [f"### {title}", "", "| path | purpose |", "|---|---|"]
    out += [f"| `{p}` | {d} |" for p, d in rows]
    return "\n".join(out) + "\n"


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    if MARK in text:
        print("already appended")
        return 0
    block = "\n" + MARK + "\n\n" + "\n".join([
        "Created today under `C:\\abrasax`. Verifiers read state and change nothing;",
        "actors change state; every actor keeps a `.bak` of what it edited.",
        "",
        table("Verifiers (read-only)", VERIFIERS),
        table("Actors (change state, gated)", ACTORS),
        table("Logs (machine record)", LOGS),
        "Deleting a log loses the evidence for a claim in this document.",
    ])
    DOC.write_text(text.rstrip() + "\n" + block, encoding="utf-8")
    print(f"appended index; doc now {len(DOC.read_text(encoding='utf-8'))} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
