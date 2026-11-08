$ErrorActionPreference = 'Continue'
$env:ABRASAX_GH_PAT = 'REDACTED_REVOKE_IN_GITHUB_SETTINGS'
Set-Location 'C:\ABRASAX'
python -u SCRIPTS\automation\mesh_runner.py
