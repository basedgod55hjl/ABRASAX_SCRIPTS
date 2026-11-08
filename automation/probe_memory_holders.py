"""Measure who holds RAM and VRAM, so reclamation decisions are evidence-based.

Measured at start of this task:
    RAM   15.36 GB total, 0.63 GB free  (96% used)
    VRAM   6.14 GB total, 5.44 GB used, 0.52 GB free, GPU 6% utilisation

Two resources near saturation at once. Before killing anything, establish:
  1. which processes are actually holding the VRAM (nvidia-smi per-process)
  2. which processes are ORPHANS (parent dead) versus live children of a live app
  3. what each candidate does for the system, so "maximum throughput" is not
     destroyed by a blind reaper

Reading only. Kill decisions belong to the manager, with thresholds.
"""
import os
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL,
                           creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "(timeout)"


print("=== GPU ===")
print(run(["nvidia-smi",
           "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
           "--format=csv,noheader"]).strip())

print("\n=== VRAM per process ===")
app = run(["nvidia-smi",
           "--query-compute-apps=pid,process_name,used_memory",
           "--format=csv,noheader"])
if app.strip():
    for line in app.strip().splitlines():
        print("  " + line)
else:
    print("  (nvidia-smi reports no compute apps -- the holder may be a graphics context)")

print("\n=== top RAM consumers with parentage ===")
ps = (
    "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 | "
    "ForEach-Object { $c = Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\" -EA 0; "
    "\"{0}|{1}|{2}|{3}\" -f $_.Id, [math]::Round($_.WorkingSet64/1MB,0), $_.ProcessName, "
    "$(if($c){$c.ParentProcessId}else{0}) }"
)
rows = []
for line in run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]).splitlines():
    parts = line.split("|")
    if len(parts) == 4:
        rows.append((int(parts[0]), int(parts[1]), parts[2], int(parts[3])))

for pid, mb, name, ppid in rows:
    alive = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 f"if (Get-Process -Id {ppid} -EA 0) {{'1'}} else {{'0'}}"]).strip()
    state = "parent-alive" if alive == "1" else "ORPHAN"
    print(f"  {pid:7d} {mb:6d} MB  {name:20s} ppid={ppid:7d} {state}")

print("\n=== node / python / llama / unity inventory ===")
for fam in ("llama-server", "node", "python", "pythonw", "Unity", "Unity.DataStore",
            "dotnet", "LM Studio"):
    out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
               f"@(Get-Process '{fam}' -EA 0).Count"]).strip()
    try:
        n = int(out)
    except ValueError:
        n = 0
    if n:
        tot = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                   f"[math]::Round(((Get-Process '{fam}' -EA 0 | Measure-Object WorkingSet64 -Sum).Sum)/1MB,0)"])
        print(f"  {fam:16s} count={n:<3} total={tot.strip()} MB")

sys.exit(0)
