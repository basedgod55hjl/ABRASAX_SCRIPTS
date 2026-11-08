"""fix_autonomy_probe_auth.py - LM Studio answers 401 without its key, so "down" was a lie.

MEASURED 2026-11-01T19:09Z:

    :1234 listening (1 listener), supervisor tick says lmstudio up,
    abrasax.autonomy says lmstudio=down and chose mode=local_only on that basis.

Cause: the probe did a bare GET /v1/models. LM Studio requires
`Authorization: Bearer $LM_STUDIO_API_KEY` (documented in providers.json since
0.4), so the probe received 401, urllib raised HTTPError, and the provider was
recorded as absent. A 401 means the server IS there - it is a policy answer, not
a health failure, exactly like `services.py` already treats it.

Also: `neo` is flagged local:true but has no base_url (it is a native adapter,
reachable only by an explicit model id), so probing it produced a permanent
"down" that meant nothing. Only HTTP-reachable locals are probed now.

Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(r"C:\abrasax\abrasax\autonomy.py")

OLD_IDS = '''def local_ids(cfg: dict | None = None) -> list[str]:
    cfg = cfg or _config()
    return [name for name, prov in (cfg.get("providers") or {}).items()
            if isinstance(prov, dict) and prov.get("local")]'''
NEW_IDS = '''def local_ids(cfg: dict | None = None) -> list[str]:
    """Local providers that can actually answer over HTTP.

    `neo` is local:true but is a native adapter with no base_url - it is reached
    only by an explicit model id, so probing it would report a permanent "down"
    that means nothing.
    """
    cfg = cfg or _config()
    return [name for name, prov in (cfg.get("providers") or {}).items()
            if isinstance(prov, dict) and prov.get("local") and prov.get("base_url")]'''

OLD_PROBE = '''    for name in local_ids(cfg):
        prov = cfg["providers"][name]
        base = prov.get("base_url") or ""
        if not base:
            out[name] = False
            continue
        try:
            with urllib.request.urlopen(base.rstrip("/") + "/models",
                                        timeout=timeout) as r:
                out[name] = r.status == 200
        except (urllib.error.URLError, OSError):
            out[name] = False
    return out'''
NEW_PROBE = '''    for name in local_ids(cfg):
        base = (cfg["providers"][name].get("base_url") or "").rstrip("/")
        req = urllib.request.Request(base + "/models")
        key = _key_for(cfg["providers"][name])
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out[name] = r.status == 200
        except urllib.error.HTTPError as exc:
            # 401/403 = the listener answered; auth is a policy decision, and a
            # provider we can talk to is UP. services.py counts it the same way.
            out[name] = exc.code < 500
        except (urllib.error.URLError, OSError):
            out[name] = False
    return out


def _key_for(prov: dict) -> str | None:
    """The API key from the environment/.env, using the router's own loader."""
    try:
        from agents.agents_hub import llm_router as _router
        keys = _router._api_keys(prov)  # noqa: SLF001 - one loader, one truth
        return keys[0] if keys else None
    except Exception:  # noqa: BLE001
        names = prov.get("api_key_env")
        names = names if isinstance(names, list) else [names] if names else []
        for n in names:
            v = os.environ.get(str(n))
            if v:
                return v
        return None'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    before = src
    for old, new in ((OLD_IDS, NEW_IDS), (OLD_PROBE, NEW_PROBE)):
        if new in src:
            continue
        if src.count(old) != 1:
            raise SystemExit(f"anchor {src.count(old)}x: {old[:60]!r}")
        src = src.replace(old, new, 1)
    if src != before:
        TARGET.write_text(src, encoding="utf-8", newline="")
        print("patched", TARGET)
    else:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
