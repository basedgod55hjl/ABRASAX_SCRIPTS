"""Replace `timeout /t N` in launchers with a portable sleep.

MEASURED (probe_timeout_forms.py), inside a detached process with no console:

    timeout /t 1                    rc=1  ERROR: Input redirection is not supported
    timeout /t 1 >nul               rc=1  ERROR: Input redirection is not supported
    timeout /t 1 /nobreak >nul      rc=1  ERROR: Input redirection is not supported
    ping -n 2 127.0.0.1 >nul        rc=0  1.17 s
    powershell Start-Sleep 1        rc=0  1.91 s

All three timeout forms fail, including /nobreak. timeout.exe is a console
program: it needs stdin to be a console handle regardless of /nobreak or where
stdout goes. My first hypothesis (that `>nul` was the trigger) was wrong --
testing all forms is what settled it.

Launchers run under Task Scheduler and detached `start` calls, where there is no
console, so every one of these 24 sleeps is a potential hard stop.

Replacement: `ping -n <N+1> 127.0.0.1 >nul`
  * ping is present on every Windows install
  * it sleeps N seconds using the loopback address, which never touches the network
  * it works with or without a console
  * -n takes packet count, and the first packet is sent immediately, hence N+1
  * /nobreak has no equivalent and is not needed

Dry-run by default; --apply writes .bak- copies first.
"""
import os
import re
import shutil
import sys
import time

SCRIPTS = r"C:\ABRASAX\SCRIPTS"
APPLY = "--apply" in sys.argv

# timeout /t 5 /nobreak >nul   ->   ping -n 6 127.0.0.1 >nul
PATTERN = re.compile(
    r'timeout\s+/t\s+(\d+)(?:\s+/nobreak)?(?:\s*>\s*nul)?',
    re.IGNORECASE)


def to_ping(m):
    n = int(m.group(1))
    return f"ping -n {n + 1} 127.0.0.1 >nul"


targets = []
for dp, dn, fns in os.walk(SCRIPTS):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for fn in fns:
        if fn.lower().endswith((".bat", ".cmd")):
            targets.append(os.path.join(dp, fn))

print(f"scanning {len(targets)} .bat/.cmd file(s)")

total_files = 0
total_subs = 0
for full in targets:
    try:
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    hits = PATTERN.findall(text)
    if not hits:
        continue
    rel = os.path.relpath(full, SCRIPTS)
    new = PATTERN.sub(to_ping, text)
    n = len(hits)
    total_files += 1
    total_subs += n
    print(f"  {rel}: {n} sleep(s)")

    if APPLY:
        backup = full + ".bak-" + time.strftime("%Y%m%d-%H%M")
        shutil.copy2(full, backup)
        open(full, "w", encoding="utf-8", newline="").write(new)

print(f"\n{total_files} file(s), {total_subs} sleep(s)")

if not APPLY:
    print("dry run -- re-run with --apply to rewrite")
    sys.exit(0)

# verify none remain
remaining = 0
for full in targets:
    try:
        text = open(full, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    remaining += len(PATTERN.findall(text))
print(f"remaining `timeout /t` in launchers: {remaining}")
sys.exit(0 if remaining == 0 else 1)
