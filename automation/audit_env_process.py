"""Audit: ENVIRONMENT, SHELL & PROCESS MANAGEMENT for C:\\ABRASAX.

Section 1 of a system build spec. Audits what actually exists rather than
restating what a doc claims.

Checks:
  A. shell + OS baseline
  B. orphaned / duplicated processes (the class of bug that cost memory twice
     tonight: three Unity editors left running at 1.5 GB)
  C. long-lived background loops and whether they have a pid file / heartbeat
  D. duplicated singleton work (multiple fb_server, multiple alive_bind)
  E. environment variables the system depends on, and whether they are set
  F. PATH hygiene -- interpreters that scripts assume

Exit 0 = no defects found. Exit 1 = at least one defect, printed.
"""
import json
import os
import subprocess
import sys
from collections import Counter

DEFECTS = []


def run_ps(script: str) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, text=True)
    return (r.stdout or "").strip()


def header(t):
    print(f"\n=== {t} ===")


# ---------------------------------------------------------------- A. baseline
header("A. SHELL / OS")
print(run_ps("'PS ' + $PSVersionTable.PSVersion + ' ' + $PSVersionTable.PSEdition"))
print(run_ps("(Get-CimInstance Win32_OperatingSystem).Caption + ' build ' + "
             "(Get-CimInstance Win32_OperatingSystem).BuildNumber"))
print("user      :", run_ps("whoami"))
print("elevated  :", run_ps(
    "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::"
    "GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"))
print("cwd       :", os.getcwd())

# ------------------------------------------------- B. duplicate singletons
header("B. DUPLICATE SINGLETONS")
raw = run_ps(
    "Get-CimInstance Win32_Process | Where-Object { $_.Name -in "
    "@('fb_server.exe','cmd.exe','python.exe','pythonw.exe') } | "
    "ForEach-Object { \"{0}|{1}|{2}\" -f $_.ProcessId, $_.ParentProcessId, $_.CommandLine }")

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
            print(f"      root pid {pid}: {cmd[:110]}")

# -------------------------------------------------- C. supervised loops
header("C. BACKGROUND LOOPS AND HEARTBEATS")
LOGS = r"C:\ABRASAX\LOGS"
for name, pidfile in (("supervisor", "supervisor.pid"),
                      ("ops_monitor", "ops_monitor.pid"),
                      ("build_loop", "build_loop.pid")):
    p = os.path.join(LOGS, pidfile)
    if os.path.exists(p):
        pid = open(p).read().strip()
        alive = run_ps(f"if (Get-Process -Id {pid} -EA 0) {{'yes'}} else {{'no'}}")
        print(f"  {name:14s} pid={pid:<7} alive={alive}")
    else:
        print(f"  {name:14s} NO PID FILE")
        DEFECTS.append(f"{name}: no pid file")

hb = os.path.join(LOGS, "alive-bind.jsonl")
if os.path.exists(hb):
    lines = open(hb, encoding="utf-8").read().strip().splitlines()
    ok = sum(1 for ln in lines if '"ok": true' in ln)
    print(f"  alive-bind heartbeat: {len(lines)} cycles, {ok} ok, "
          f"{len(lines) - ok} failed")
    if ok != len(lines):
        DEFECTS.append(f"alive-bind: {len(lines) - ok} failed cycles")
else:
    print("  alive-bind heartbeat: MISSING")
    DEFECTS.append("alive-bind: no heartbeat file")

ops = os.path.join(LOGS, "ops-state.json")
if os.path.exists(ops):
    st = json.load(open(ops, encoding="utf-8"))
    print(f"  ops-state signature : {st.get('signature')}  ts={st.get('ts')}")
    if st.get("signature") != "healthy":
        DEFECTS.append(f"ops-state signature={st.get('signature')}")

# ------------------------------------------------ D. stale pid files
header("D. PID FILE HYGIENE")
for fn in ("supervisor.pid", "ops_monitor.pid", "build_loop.pid"):
    p = os.path.join(LOGS, fn)
    if not os.path.exists(p):
        continue
    pid = open(p).read().strip()
    cmd = run_ps(f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" -EA 0).CommandLine")
    if not cmd:
        print(f"  {fn}: pid {pid} is DEAD but the file remains -> stale")
        DEFECTS.append(f"stale pid file {fn} (pid {pid} dead)")
    else:
        print(f"  {fn}: pid {pid} live")

# ------------------------------------------------ E. environment
header("E. ENVIRONMENT VARIABLES")
needed = ["NVIDIA_API_KEY", "JEV_API_KEY", "JEV_BASE_URL", "NVIDIA_MODEL",
          "ABRASAX_GATEWAY_TOKEN", "ABRASAX_WEBHOOK_SECRET"]
for k in needed:
    v = os.environ.get(k)
    if v:
        print(f"  {k:24s} set (len {len(v)})")
    else:
        # not a defect: the gateway is open by design on loopback
        print(f"  {k:24s} unset")

envf = r"C:\ABRASAX\.env"
if os.path.exists(envf):
    keys = [ln.split("=", 1)[0] for ln in open(envf, encoding="utf-8", errors="replace")
            if "=" in ln and not ln.strip().startswith("#")]
    print(f"  .env present with {len(keys)} keys")
else:
    print("  .env MISSING")
    DEFECTS.append(".env missing")

# ------------------------------------------------ F. interpreters
header("F. INTERPRETERS ON PATH")
for exe in (r"C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe",):
    print(f"  {exe}: {'present' if os.path.exists(exe) else 'MISSING'}")
    if not os.path.exists(exe):
        DEFECTS.append(f"missing interpreter {exe}")

# ------------------------------------------------ summary
header("SUMMARY")
if DEFECTS:
    print(f"{len(DEFECTS)} defect(s):")
    for d in DEFECTS:
        print("  - " + d)
    print("\nRESULT: DEFECTS FOUND")
    sys.exit(1)

print("no defects found")
print("\nRESULT: PASS")
sys.exit(0)
