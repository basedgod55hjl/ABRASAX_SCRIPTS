"""Fix audit_env_process.py section B: count process ROOTS, not matching PIDs.

The audit reported 2 defects (alive_bind x2, imgui_overlay x2). Both were false:
the measured tree for each was

    cmd.exe -> python.exe (venv shim) -> python.exe (uv interpreter)

i.e. ONE instance behind three PIDs. Windows venv shims are launchers, and
`start /min "" cmd /c "..."` adds a cmd wrapper, so this is normal.

This is the fifth time tonight a red result was the checker's fault. Fixing the
checker rather than "fixing" the system is the whole point.

The fix: build a pid -> ppid map over all matching processes, then count parents
that are NOT themselves in the matched set. That count is the number of real
instances.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\audit_env_process.py"
src = open(PATH, encoding="utf-8").read()

if "count_roots" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = '''raw = run_ps(
    "Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
    "@('fb_server.exe','python.exe','pythonw.exe') } | "
    "ForEach-Object { \\"{0}|{1}\\" -f $_.ProcessId, $_.CommandLine }")

procs = []
for line in raw.splitlines():
    if "|" not in line:
        continue
    pid, cmd = line.split("|", 1)
    procs.append((pid.strip(), cmd))

def count_matching(token):
    return [p for p in procs if token in p[1]]

for token, expected in (("fb_server.exe", 1),
                        ("alive_bind.py", 1),
                        ("imgui_overlay.py", 1),
                        ("string_brain.py", None)):
    hits = count_matching(token)
    n = len(hits)
    status = "ok"
    if token == "string_brain.py":
        # transient: 0 or 1 is fine, more is not
        if n > 1:
            status = "DEFECT"
    elif n != expected:
        status = "DEFECT"
    print(f"  {token:22s} count={n:<3} expected={expected}  {status}")
    if status == "DEFECT":
        DEFECTS.append(f"{token}: {n} running, expected {expected}")
        for pid, cmd in hits:
            print(f"      pid {pid}: {cmd[:120]}")'''

NEW = '''raw = run_ps(
    "Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
    "@('fb_server.exe','cmd.exe','python.exe','pythonw.exe') } | "
    "ForEach-Object { \\"{0}|{1}|{2}\\" -f $_.ProcessId, $_.ParentProcessId, $_.CommandLine }")

procs = []   # (pid, ppid, cmdline)
for line in raw.splitlines():
    parts = line.split("|", 2)
    if len(parts) == 3:
        procs.append((parts[0].strip(), parts[1].strip(), parts[2]))


def count_roots(token):
    """Number of independent instances of `token`.

    Counting matching PIDs overcounts on Windows: the venv python.exe is a launcher
    that spawns the real interpreter, and `cmd /c` adds another wrapper, so one
    instance legitimately shows up as 3 PIDs. The truth is the number of processes
    whose PARENT is not itself part of the match.
    """
    hits = [p for p in procs if token in p[2]]
    pids = {p[0] for p in hits}
    roots = [p for p in hits if p[1] not in pids]
    return roots, hits


for token, expected in (("fb_server.exe", 1),
                        ("alive_bind.py", 1),
                        ("imgui_overlay.py", 1),
                        ("string_brain.py", None)):
    roots, hits = count_roots(token)
    n = len(roots)
    status = "ok"
    if token == "string_brain.py":
        if n > 1:
            status = "DEFECT"
    elif n != expected:
        status = "DEFECT"
    print(f"  {token:22s} instances={n:<3} pids={len(hits):<3} expected={expected}  {status}")
    if status == "DEFECT":
        DEFECTS.append(f"{token}: {n} instance(s), expected {expected}")
        for pid, ppid, cmd in roots:
            print(f"      root pid {pid}: {cmd[:110]}")'''

if OLD not in src:
    print("ANCHOR-NOT-FOUND: section B block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: section B now counts process roots")
