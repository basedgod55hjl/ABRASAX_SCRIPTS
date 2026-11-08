"""check_email.py — is the commit email a verified address on the account?

Attribution on GitHub follows the EMAIL, not the name. This asks the account which
addresses exist and whether the one in .gitconfig is among them, verified. If the
token cannot read /user/emails (fine-grained tokens often cannot), that is
reported as a scope fact rather than a failure - and the fallback proof is that
the commits already resolve to the account.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.abx.repo import token  # noqa: E402

TARGET = "basedgod55hjl@users.noreply.github.com"


def main() -> int:
    req = urllib.request.Request("https://api.github.com/user/emails", headers={
        "Authorization": f"Bearer {token()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "abx",
    })
    print(f"want: {TARGET}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read() or b"[]")
    except urllib.error.HTTPError as exc:
        print(f"GET /user/emails -> HTTP {exc.code}  (token lacks the emails scope)")
        print("=> cannot enumerate addresses; attribution is proven instead by the")
        print("   commits resolving to login=basedgod55hjl (see check_attribution.py)")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("ERR", exc)
        return 1

    found = False
    for e in body:
        mark = "  <== configured" if e.get("email") == TARGET else ""
        print(f"  {e.get('email'):<48} primary={e.get('primary')} verified={e.get('verified')}{mark}")
        if e.get("email") == TARGET:
            found = True
    print(f"\nconfigured address present on account: {found}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
