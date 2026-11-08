$ErrorActionPreference = 'SilentlyContinue'
$root = "$env:USERPROFILE\.lmstudio\models"
$rows = @()
Get-ChildItem $root -Recurse -Filter '*.gguf' -File | ForEach-Object {
    $kind = if ($_.Name -match '^mmproj') { 'projector' }
            elseif ($_.Name -match '^mtp-') { 'mtp' }
            else { 'model' }
    $rows += [pscustomobject]@{
        kind    = $kind
        size_gb = [math]::Round($_.Length / 1GB, 2)
        name    = $_.Name
        dir     = $_.Directory.Name
    }
}
$rows | Sort-Object kind, size_gb -Descending | Format-Table -AutoSize
Write-Host ("`ntotal gguf: " + $rows.Count)
Write-Host ("main models: " + ($rows | Where-Object { $_.kind -eq 'model' }).Count)
$rows | ConvertTo-Json -Depth 4 | Set-Content -Path 'C:\ABRASAX\logs\gguf_inventory.json' -Encoding UTF8
