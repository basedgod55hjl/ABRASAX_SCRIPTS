# who_owns_that_log.ps1 - which Chrome extension owns the LevelDB log that kills findstr?
#
# The offending file is AppData\...\Default\Local Extension Settings\<id>\000003.log.
# If that id belongs to an extension that is no longer installed, its storage is
# orphaned and clearing it removes the obstruction for good. If it is a live
# extension, the file must be excluded instead - deleting it would wipe the
# extension's saved state.

$id    = 'hkdmdpdhfaamhgaojpelccmeehpfljgf'
$ud    = 'C:\Users\lucar\AppData\Local\Google\Chrome\User Data\Default'
$items = @(
  @{ Name = 'Local Extension Settings'; Path = Join-Path $ud "Local Extension Settings\$id" },
  @{ Name = 'Extension install dir';    Path = Join-Path $ud "Extensions\$id" },
  @{ Name = 'Sync Extension Settings';  Path = Join-Path $ud "Sync Extension Settings" },
  @{ Name = 'Extension State';          Path = (Join-Path $ud 'Extension State') }
)

foreach ($i in $items) {
  Write-Output ("=== " + $i.Name)
  if (Test-Path $i.Path) {
    Get-ChildItem $i.Path -Force -ErrorAction SilentlyContinue |
      Select-Object -First 8 Name, Length, LastWriteTime | Format-Table -AutoSize
  } else {
    Write-Output "    absent: $($i.Path)"
  }
}

$log = Join-Path $ud "Local Extension Settings\$id\000003.log"
Write-Output "=== offending file"
if (Test-Path $log) {
  $f = Get-Item $log
  Write-Output ("    {0:N1} MB, modified {1}" -f ($f.Length / 1MB), $f.LastWriteTime)
} else {
  Write-Output "    gone"
}

# any manifest referencing this id tells us the extension name
Write-Output "=== manifests mentioning the id"
$found = $false
Get-ChildItem $ud -Recurse -File -Filter manifest.json -Depth 4 -Force -ErrorAction SilentlyContinue |
  ForEach-Object {
    if ((Select-String -Path $_.FullName -Pattern $id -SimpleMatch -Quiet -ErrorAction SilentlyContinue)) {
      $found = $true
      Write-Output ("    " + $_.FullName)
    }
  }
if (-not $found) { Write-Output "    none (extension not installed under this profile)" }
