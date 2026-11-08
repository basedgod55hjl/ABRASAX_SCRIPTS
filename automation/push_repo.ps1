$ErrorActionPreference = 'Continue'
# Use the token in the remote URL for this push only; do not persist it.
$env:GIT_TERMINAL_PROMPT = '0'
Set-Location 'C:\ABRASAX'

$tok = 'REDACTED_REVOKE_IN_GITHUB_SETTINGS'
$url = "https://x-access-token:$tok@github.com/basedgod55hjl/ABRASAX-REBUILD.git"

Write-Host "=== pushing HEAD:main ==="
git push $url HEAD:main 2>&1

Write-Host "`n=== verify ==="
git ls-remote --heads origin 2>&1 | Select-Object -First 3
git rev-parse --short HEAD
