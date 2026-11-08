"""Report the live state of the floating-brain overlay: processes + renderer health.

Read-only. Uses CIM for command-line filtering (avoids PowerShell quoting) and a
short-timeout HTTP probe so a hung renderer cannot block the caller.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

RENDER = "http://127.0.0.1:9700"

PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'imgui_overlay'
} | ForEach-Object {
    '{0}`t{1}`t{2}' -f $_.ProcessId, $_.Name, $_.CommandLine
}
"""


def overlay_procs() -> list[tuple[int, str, str]]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
        capture_output=True, text=True, timeout=60,
    ).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].strip().isdigit():
            rows.append((int(parts[0]), parts[1], parts[2]))
    return rows


def get(path: str):
    try:
        with urllib.request.urlopen(RENDER + path, timeout=4) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type", "")
            return r.status, ctype, body
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:  # noqa: BLE001 - probe must never raise
        return None, type(e).__name__, str(e).encode()


def main() -> int:
    procs = overlay_procs()
    print(f"overlay processes: {len(procs)}")
    for pid, name, cl in procs:
        print(f"  pid={pid} {name}")
        print(f"    {cl[:160]}")

    for path in ("/health", "/state"):
        status, ctype, body = get(path)
        print(f"GET {RENDER}{path} -> {status} {ctype} {len(body)} B")
        if status == 200 and "json" in ctype:
            try:
                data = json.loads(body)
                keys = sorted(data)[:12]
                print(f"    keys: {keys}")
            except Exception:  # noqa: BLE001
                pass

    status, ctype, body = get("/frame.png")
    print(f"GET {RENDER}/frame.png -> {status} {ctype} {len(body)} B")
    png_ok = body[:8] == b"\x89PNG\r\n\x1a\n"
    print(f"    png signature: {png_ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
