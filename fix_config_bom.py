"""fix_config_bom.py - a BOM in providers.json took the whole router offline.

MEASURED 2026-11-01T19:2xZ:

    >>> from agents.agents_hub import llm_router as R
    >>> R._config()
    json.decoder.JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig)

    00: EF BB BF 7B      <- providers.json starts with a UTF-8 BOM

Every route goes through `_config()`, so the gateway, the agents and the build
loop all failed at the first line of the only file that says where to send a
prompt. Nothing in this tree writes a BOM (`json.dumps` + utf-8 does not), so the
file was rewritten by an external tool - PowerShell's `Set-Content`/`Out-File`
does exactly this in 5.1.

Two fixes, both needed:

1. The readers tolerate a BOM (`utf-8-sig`). A config file is input from other
   tools; refusing to read it over three invisible bytes is not a security
   property.
2. The file itself is rewritten without the BOM, so anything else that reads it
   naively (node, dotnet, grep) sees plain JSON.

Idempotent: re-running changes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\abrasax")
CFG = ROOT / "CONFIG" / "llm" / "providers.json"

READERS = {
    ROOT / "agents" / "agents_hub" / "llm_router.py": [
        ('return json.loads(_CFG.read_text(encoding="utf-8"))',
         'return json.loads(_CFG.read_text(encoding="utf-8-sig"))'),
    ],
    ROOT / "abrasax" / "autonomy.py": [
        ('return json.loads(CFG.read_text(encoding="utf-8"))',
         'return json.loads(CFG.read_text(encoding="utf-8-sig"))'),
    ],
    ROOT / "abrasax" / "gateway.py": [
        ('with open(ROOT / "CONFIG" / "llm" / "providers.json", encoding="utf-8") as f:',
         'with open(ROOT / "CONFIG" / "llm" / "providers.json", encoding="utf-8-sig") as f:'),
    ],
}

BOM = b"\xef\xbb\xbf"


def main() -> int:
    changed = []
    for path, pairs in READERS.items():
        src = path.read_text(encoding="utf-8")
        before = src
        for old, new in pairs:
            if new in src:
                continue
            n = src.count(old)
            if n == 0:
                continue
            src = src.replace(old, new)
            print(f"{path.name}: {n} reader(s) -> utf-8-sig")
        if src != before:
            path.write_text(src, encoding="utf-8", newline="")
            changed.append(path)

    raw = CFG.read_bytes()
    if raw.startswith(BOM):
        text = raw[len(BOM):].decode("utf-8")
        data = json.loads(text)          # must parse before we write
        CFG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="")
        print("providers.json: BOM stripped and re-serialised")
        changed.append(CFG)

    # The gateway also reads it inline at two more places; normalise those too.
    gw = ROOT / "abrasax" / "gateway.py"
    src = gw.read_text(encoding="utf-8")
    if 'providers.json", encoding="utf-8"' in src:
        src = src.replace('providers.json", encoding="utf-8"',
                          'providers.json", encoding="utf-8-sig"')
        gw.write_text(src, encoding="utf-8", newline="")
        print("gateway.py: remaining readers normalised")
        changed.append(gw)

    for p in changed:
        print("patched", p)
    if not changed:
        print("already applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
