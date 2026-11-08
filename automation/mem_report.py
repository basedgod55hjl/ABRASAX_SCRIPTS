"""Report what is actually eating the machine's memory.

Measured fault: total physical 15.4 GB, free 0.4 GB. The Unity Data Store asks for
a 1 GB shared-memory region and stalls at 'Starting Unity Data Store Application'
because it cannot get it. That, not the project, is why the editor never reaches
compilation.

Prints the top consumers so the fix is evidence-driven.
"""
import subprocess
import sys

ps = r"""
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize/1MB,2)
$freeGB  = [math]::Round($os.FreePhysicalMemory/1MB,2)
"total={0}GB free={1}GB used={2}%" -f $totalGB,$freeGB,[math]::Round(($totalGB-$freeGB)/$totalGB*100,1)
""
"TOP 20 BY WORKING SET"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 20 |
  ForEach-Object {
    "{0,-32} {1,8:N0} MB  pid={2}" -f $_.ProcessName, ($_.WorkingSet64/1MB), $_.Id
  }
""
"GROUPED BY NAME"
Get-Process | Group-Object ProcessName | ForEach-Object {
  [pscustomobject]@{
    Name  = $_.Name
    Count = $_.Count
    MB    = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum)/1MB,0)
  }
} | Sort-Object MB -Descending | Select-Object -First 12 |
  ForEach-Object { "{0,-32} n={1,-3} {2,8:N0} MB" -f $_.Name,$_.Count,$_.MB }
"""

r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr)
sys.exit(0)
