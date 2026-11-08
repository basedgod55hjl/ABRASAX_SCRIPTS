# recycle_bins.ps1 — size every volume's $Recycle.Bin.
# Files "deleted" on a drive still occupy that drive until the bin is emptied,
# which makes this one of the few places where GB hide with no visible owner.
$rows = @()
foreach ($d in 'C:', 'I:', 'F:', 'G:', 'E:', 'H:', 'D:') {
  $p = Join-Path $d '$Recycle.Bin'
  if (Test-Path -LiteralPath $p) {
    $files = Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue
    $bytes = ($files | Measure-Object Length -Sum).Sum
    $rows += [pscustomobject]@{
      Drive = $d
      GB    = [math]::Round($bytes / 1GB, 2)
      Files = $files.Count
      Newest = ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
    }
  } else {
    $rows += [pscustomobject]@{ Drive = $d; GB = 'absent'; Files = 0; Newest = $null }
  }
}
$rows | Sort-Object { if ($_.GB -is [double]) { $_.GB } else { -1 } } -Descending | Format-Table -AutoSize
"total reclaimable: {0:N2} GB" -f (($rows | Where-Object { $_.GB -is [double] } | Measure-Object GB -Sum).Sum)
