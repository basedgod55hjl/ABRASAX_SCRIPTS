"""ci_logs.py — pull the failing job's log for a rebuilt repo's CI run.

GET /repos/{owner}/{repo}/actions/runs/{id}/logs returns a ZIP of per-step logs.
The toolkit's _api() assumes JSON, so this does its own authenticated fetch and
prints only the tail of the failing step.

    python SCRIPTS/ci_logs.py ABRASAX-UI
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, token  # noqa: E402


def fetch_zip(url: str) -> bytes | None:
    tok = token()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "abx-ci",
    })
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  fetch failed: {exc}")
        return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: ci_logs.py <repo> [repo...]")
        return 2
    for name in argv:
        full = f"basedgod55hjl/{name}"
        runs = _api(f"/repos/{full}/actions/runs?per_page=1").get("body") or {}
        items = runs.get("workflow_runs") or []
        if not items:
            print(f"{name}: no runs")
            continue
        run = items[0]
        print(f"\n=== {name} run {run['id']} ({run.get('conclusion')})")
        blob = fetch_zip(f"https://api.github.com/repos/{full}/actions/runs/{run['id']}/logs")
        if not blob:
            continue
        try:
            zf = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile:
            print("  logs not a zip (run may still be in flight)")
            continue
        for info in zf.infolist():
            if not info.filename.lower().endswith(".txt"):
                continue
            text = zf.read(info).decode("utf-8", "replace")
            if "##[error]" not in text and "error" not in text.lower():
                continue
            lines = [ln for ln in text.splitlines() if ln.strip()]
            print(f"  --- {info.filename}")
            for ln in lines[-18:]:
                print("    " + ln[:200])
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
