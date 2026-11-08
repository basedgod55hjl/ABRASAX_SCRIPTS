param([Parameter(Mandatory = $true)][string]$Ts)
$ErrorActionPreference = "Stop"
$Py = "C:\Users\lucar\AppData\Local\hermes\installs\963bca82cc65020c\environments\5c935fe120f64309965c21d03cf4ab9b\venv\Scripts\python.exe"
$Script = "C:\abrasax\scripts\drive_walk.py"
$OutDir = "C:\abrasax\LOGS\subagents"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path "C:\abrasax\DATA" | Out-Null
$p = Start-Process -FilePath $Py -ArgumentList @($Script, $Ts) `
    -WorkingDirectory "C:\abrasax\scripts" -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $OutDir "drive_walk_$Ts.out.log") `
    -RedirectStandardError (Join-Path $OutDir "drive_walk_$Ts.err.log") `
    -PassThru
Write-Output "PID=$($p.Id)"
