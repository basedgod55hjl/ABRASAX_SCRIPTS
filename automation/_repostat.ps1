$ErrorActionPreference = 'Continue'
$env:GH_TOKEN = 'REDACTED_REVOKE_IN_GITHUB_SETTINGS'
Set-Location 'C:\ABRASAX'

Write-Host "=== local HEAD ==="
git rev-parse --short HEAD
git log --oneline -1

Write-Host "`n=== remote ==="
git ls-remote --heads origin 2>&1 | Select-Object -First 5

Write-Host "`n=== ahead/behind ==="
git rev-list --left-right --count origin/main...HEAD 2>&1

Write-Host "`n=== uncommitted files ==="
(git status --porcelain | Measure-Object).Count
