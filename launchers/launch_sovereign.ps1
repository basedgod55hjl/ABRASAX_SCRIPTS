# launch_sovereign.ps1 — Ignite the Crystal
$ErrorActionPreference = "Stop"
Set-Location C:\ABRASAX
$py = "C:\ABRASAX\PYTHON\.venv_gui\Scripts\python.exe"
Write-Host "[sovereign] proof of discovery..."
& $py -m abrasax sovereign proof
Write-Host "[sovereign] ignition..."
& $py -m abrasax sovereign ignite
Write-Host "[sovereign] booting runtime..."
& $py -m abrasax boot
Write-Host "[sovereign] gateway health:"
try { (Invoke-WebRequest -Uri http://127.0.0.1:9001/health -UseBasicParsing -TimeoutSec 5).Content } catch { Write-Host "gateway offline (supervisor will start it)" }
