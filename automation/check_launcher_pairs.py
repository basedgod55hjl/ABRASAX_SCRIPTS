"""Fix the duplicate-detection logic: count interpreter chains, not every match.

The checker reported "MORE THAN 2 = real duplicate" for alive_bind and
imgui_overlay. Both were wrong. The actual tree measured was:

    cmd.exe (ppid external)
      └─ python.exe  (venv shim)          PYTHON\\.venv_gui\\Scripts\\python.exe
           └─ python.exe (uv interpreter) ...\\uv\\python\\cpython-3.11.15\\python.exe

That is ONE instance behind three processes. On Windows the venv python.exe is a
launcher, and `start /min "" cmd /c "..."` adds a cmd wrapper, so 3 PIDs for one
logical process is expected and correct.

The right rule: build the parent/child graph, take only the ROOT of each chain
(the process whose parent is not itself part of the group), and count roots.
One root = one instance.

Exit 0 when every script has exactly one root.
"""
import subprocess
import sys
from collections import defaultdict

SCRIPT = r"""
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'alive_bind|imgui_overlay|fb_server' } |
  ForEach-Object {
    "{0}|{1}|{2}|{3}" -f $_.ProcessId, $_.ParentProcessId, $_.Name,
      ($_.CommandLine -replace '\|',' ')
  }
"""

out = subprocess.run(["powershell", "-NoProfile", "-Command", SCRIPT],
                     capture_output=True, text=True).stdout

rows = []
for line in out.splitlines():
    parts = line.split("|", 3)
    if len(parts) == 4:
        rows.append(tuple(p.strip() for p in parts))

by_pid = {r[0]: r for r in rows}

groups = defaultdict(list)
for pid, ppid, name, cmd in rows:
    for token in ("alive_bind", "imgui_overlay", "fb_server"):
        if token in cmd:
            groups[token].append((pid, ppid, name, cmd))

print(f"processes matching: {len(rows)}\n")

bad = 0
for token, members in sorted(groups.items()):
    pids = {m[0] for m in members}
    # roots = members whose parent is NOT in this group
    roots = [m for m in members if m[1] not in pids]

    print(f"--- {token} ---")
    print(f"  processes in chain : {len(members)}")
    print(f"  distinct instances : {len(roots)}")

    # walk each chain for the record
    children = defaultdict(list)
    for m in members:
        children[m[1]].append(m)

    def walk(pid, depth=0):
        for c in children.get(pid, []):
            print(f"    {'  ' * depth}-> pid={c[0]:<7} {c[2]}")
            walk(c[0], depth + 1)

    for r in roots:
        print(f"    root pid={r[0]:<7} {r[2]}")
        walk(r[0])

    if len(roots) != 1:
        print(f"  [DEFECT] {len(roots)} independent instances, expected 1")
        bad += 1
    else:
        print("  [PASS] exactly one instance (extra PIDs are launcher/child)")
    print()

print("RESULT:", "PASS -- one instance per service, launcher chains are expected"
      if bad == 0 else f"DEFECT -- {bad} service(s) with multiple instances")
sys.exit(0 if bad == 0 else 1)
