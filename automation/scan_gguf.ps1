$ErrorActionPreference = 'SilentlyContinue'
$out = 'C:\ABRASAX\logs\scan_gguf.json'

# LM Studio's own model index is authoritative and instant; use it first.
$lmsModels = "$env:USERPROFILE\.lmstudio\models"
Write-Host "=== LM Studio model dir ==="
Write-Host $lmsModels

$models = @()
if (Test-Path $lmsModels) {
    Get-ChildItem $lmsModels -Recurse -Filter '*.gguf' -File |
      ForEach-Object {
        $models += [pscustomobject]@{
            path = $_.FullName
            size_gb = [math]::Round($_.Length / 1GB, 3)
            modified = $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
            source = 'lmstudio'
        }
      }
}

# Also sweep the non-system drives for stray GGUFs (skip huge trees we know).
foreach ($d in @('E:','F:','G:','H:','I:')) {
    if (-not (Test-Path $d)) { continue }
    Get-ChildItem $d -Recurse -Filter '*.gguf' -File -ErrorAction SilentlyContinue |
      ForEach-Object {
        $models += [pscustomobject]@{
            path = $_.FullName
            size_gb = [math]::Round($_.Length / 1GB, 3)
            modified = $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
            source = $d
        }
      }
}

$models = $models | Sort-Object size_gb -Descending
$models | ConvertTo-Json -Depth 4 | Set-Content -Path $out -Encoding UTF8

Write-Host ("`nGGUF files found: " + $models.Count)
$models | Select-Object -First 25 | Format-Table -AutoSize
Write-Host ("wrote " + $out)
