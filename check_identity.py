"""check_identity.py — the account behind the token, end to end.

`[user] name = basedgod55hjl` in .gitconfig is only a local label; what matters is
which account the token authenticates as and whether the commits land on it.
Prints the account record, the token's scopes, and any fine-grained permissions
the API will disclose.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import _api, token  # noqa: E402


def raw(path: str) -> dict:
    req = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Authorization": f"Bearer {token()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "abx",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return {"http": r.status, "headers": dict(r.headers), "body": json.loads(r.read() or b"{}")}
    except Exception as exc:  # noqa: BLE001
        return {"http": None, "error": str(exc)}


def main() -> int:
    me = raw("/user")
    body = me.get("body") or {}
    print(f"http          {me.get('http')}")
    print(f"login         {body.get('login')}")
    print(f"name          {body.get('name')}")
    print(f"id            {body.get('id')}")
    print(f"type          {body.get('type')}")
    print(f"created_at    {body.get('created_at')}")
    print(f"public_repos  {body.get('public_repos')}")
    print(f"plan          {(body.get('plan') or {}).get('name')}")
    hdrs = me.get("headers") or {}
    scopes = hdrs.get("X-OAuth-Scopes") or hdrs.get("x-oauth-scopes")
    print(f"oauth scopes  {scopes or '(none - fine-grained token)'}")
    print(f"accepted      {hdrs.get('X-Accepted-GitHub-Permissions') or hdrs.get('x-accepted-github-permissions')}")

    for probe in ("/user/repos?per_page=1&visibility=private", "/user/installations"):
        r = raw(probe)
        print(f"{probe:<45} http={r.get('http')} {r.get('error') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
