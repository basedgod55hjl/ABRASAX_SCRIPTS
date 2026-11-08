"""ci_log_debug.py — list what the Actions logs endpoint actually returns.

The one-line version kept dying in the shell quoting layer, and an earlier run
printed nothing at all: either the fetch was refused (PAT scope) or the payload
is not the ZIP we assumed. This prints both, explicitly.
"""
from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, token  # noqa: E402


def main() -> int:
    full = "basedgod55hjl/ABRASAX-UI"
    runs = _api(f"/repos/{full}/actions/runs?per_page=1").get("body") or {}
    items = runs.get("workflow_runs") or []
    if not items:
        print("no runs")
        return 1
    run = items[0]
    url = f"https://api.github.com/repos/{full}/actions/runs/{run['id']}/logs"
    print("run", run["id"], run.get("conclusion"))
    print("url", url)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "abx",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
            print("http", r.status, "bytes", len(data), "magic", data[:4])
    except urllib.error.HTTPError as exc:
        print("HTTPError", exc.code, exc.read()[:300])
        return 1
    except Exception as exc:  # noqa: BLE001
        print("ERR", type(exc).__name__, exc)
        return 1
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        print("not a zip; first 300 bytes:")
        print(data[:300])
        return 1
    print("entries", len(zf.infolist()))
    for info in zf.infolist()[:15]:
        print("  ", info.filename, info.file_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
