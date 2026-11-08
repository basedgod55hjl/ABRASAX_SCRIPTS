$ErrorActionPreference = 'SilentlyContinue'
Write-Host "=== probe still running? ==="
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'probe_models' }
if ($p) {
    foreach ($x in $p) { Write-Host ("  pid=" + $x.ProcessId) }
} else { Write-Host "  finished" }

Write-Host "`n=== probe output so far ==="
Get-Content 'C:\ABRASAX\logs\probe_models.out'

Write-Host "`n=== stray llama-server ==="
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'llama-server.exe' } | ForEach-Object {
    $pr = Get-Process -Id $_.ProcessId
    Write-Host ("  pid={0} cpu={1}s ws={2}MB" -f $_.ProcessId, [int]$pr.CPU, [math]::Round($pr.WS/1MB))
}

Write-Host "`n=== gpu ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader
