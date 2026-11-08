$ErrorActionPreference = 'SilentlyContinue'
Write-Host "=== llama-server detail ==="
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'llama-server.exe' } | ForEach-Object {
    $pr = Get-Process -Id $_.ProcessId
    $cmd = $_.CommandLine
    if ($cmd.Length -gt 150) { $cmd = $cmd.Substring(0, 150) }
    Write-Host ("pid={0} cpu={1}s ws={2}MB" -f $_.ProcessId, [int]$pr.CPU, [math]::Round($pr.WS/1MB))
    Write-Host ("   " + $cmd)
    Write-Host ("   parent=" + $_.ParentProcessId)
}

Write-Host "`n=== model_pinner present? ==="
$pin = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'model_pinner' }
if ($pin) { foreach ($x in $pin) { Write-Host ("  pid=" + $x.ProcessId + " parent=" + $x.ParentProcessId) } }
else { Write-Host "  not running" }
