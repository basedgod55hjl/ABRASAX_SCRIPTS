:: LEGACY LAUNCHER - BROKEN, DO NOT RUN
:: Reason: targets the retired ABRASAX_GOD_OS tree
:: Measured by SCRIPTS/automation/audit_launchers.py on 2026-10-17.
:: This file is kept for reference only. The live tree is C:\ABRASAX.
# setup.ps1 - one-click ABRASAX GOD OS setup
$ErrorActionPreference = "Continue"
$root = "C:\Users\sirch\Desktop\ABRASAX_GOD_OS"

$dirs = @("config", "src\core", "src\kernels", "src\rust_core\src", "src\node_chat", "src\aixl_grammar", "src\agents", "src\telegram", "seeds", "crystals", "logs", "scripts", "training_data", "tools", "docs", ".vscode")
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $root $d) | Out-Null }

Write-Host "[OSIRISBLXCK] Installing Python deps..." -ForegroundColor Cyan
python -m pip install --quiet torch requests numpy lark

Write-Host "[OSIRISBLXCK] Installing Node deps..." -ForegroundColor Cyan
Push-Location (Join-Path $root "src\node_chat")
npm install
Pop-Location

Write-Host "[OSIRISBLXCK] Building Rust hydrator..." -ForegroundColor Cyan
Push-Location (Join-Path $root "src\rust_core")
cargo build --release
Pop-Location

Write-Host "[OSIRISBLXCK] Setup complete. Run start_god.bat" -ForegroundColor Green
