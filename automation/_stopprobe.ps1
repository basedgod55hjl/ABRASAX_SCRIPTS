$ErrorActionPreference = 'SilentlyContinue'
Write-Host "=== stop the slow full probe ==="
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'probe_models' } | ForEach-Object {
    Write-Host ("  killing " + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force
}
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'llama-server.exe' -and $_.CommandLine -match '--no-webui'
} | ForEach-Object {
    Write-Host ("  killing stray llama " + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force
}
Start-Sleep -Seconds 2
Write-Host "`n=== gpu ==="
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader
Write-Host "`n=== pinner state (should be suspended) ==="
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'model_pinner' } | ForEach-Object {
    $p = Get-Process -Id $_.ProcessId
    Write-Host ("  pid={0} cpu={1:N0}s" -f $_.ProcessId, $p.CPU)
}
