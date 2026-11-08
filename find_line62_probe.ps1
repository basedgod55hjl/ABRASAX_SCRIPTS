# find_line62_probe.ps1 - which file has long lines at 62 and 63?
#
# findstr's error incremented 62 -> 63 between two runs, which means one file has a
# RUN of overlong lines, not a single one. Reading every line of every file to find
# that is wasteful: reading the first 70 lines answers it, because the offender is
# at a known line number.
#
#   powershell -ExecutionPolicy Bypass -File SCRIPTS\find_line62_probe.ps1

$root   = 'C:\Users\lucar'
$out    = 'C:\abrasax\LOGS\line62.txt'
$target = 62
$window = 75
$rows   = @()

Get-ChildItem $root -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Length -gt 5000 -and
    $_.Length -lt 200MB -and
    $_.Extension -in '.txt', '.log', '.md', '.json', '.jsonl', '.csv', '.out', '.err'
  } |
  ForEach-Object {
    try {
      $rd = [System.IO.File]::OpenText($_.FullName)
      $n = 0
      $long62 = 0
      $long63 = 0
      while ($n -lt $window -and $null -ne ($line = $rd.ReadLine())) {
        $n++
        if ($n -eq $target) { $long62 = $line.Length }
        if ($n -eq ($target + 1)) { $long63 = $line.Length }
      }
      $rd.Close()
      if ($long62 -gt 8000 -or $long63 -gt 8000) {
        $rows += [pscustomobject]@{
          File = $_.FullName
          Line62 = $long62
          Line63 = $long63
        }
      }
    } catch { }
  }

"files with an overlong line at 62 or 63:" | Set-Content $out -Encoding UTF8
$rows | Format-Table -AutoSize | Out-String -Width 220 | Add-Content $out -Encoding UTF8
Write-Output ("DONE {0} hit(s) -> {1}" -f $rows.Count, $out)
