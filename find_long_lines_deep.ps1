# find_long_lines_deep.ps1 - find the file whose line 62 breaks findstr.
#
# The first pass only looked at the top level of the profile and found long lines
# at line 1, 3, 19 - never 62. findstr names the line, so the offender is a
# different file further down the tree. This walks the whole profile (bounded by
# extension) and reports every line over 8000 chars, sorted by line length.
#
#   powershell -ExecutionPolicy Bypass -File SCRIPTS\find_long_lines_deep.ps1

$root  = 'C:\Users\lucar'
$limit = 8000
$out   = 'C:\abrasax\LOGS\long_lines.txt'
$rows  = @()
$cap   = 20000

Get-ChildItem $root -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Extension -in '.txt', '.log', '.md', '.json', '.jsonl', '.csv', '.out', '.err', '.ps1', '.mjs', '.py' -and
    $_.Length -lt 200MB
  } |
  ForEach-Object {
    if ($rows.Count -ge $cap) { return }
    $f = $_
    try {
      $reader = [System.IO.File]::OpenText($f.FullName)
      $n = 0
      while ($null -ne ($line = $reader.ReadLine())) {
        $n++
        if ($line.Length -gt $limit) {
          $rows += [pscustomobject]@{
            File  = $f.FullName
            Line  = $n
            Chars = $line.Length
          }
          if ($rows.Count -ge $cap) { break }
        }
      }
      $reader.Close()
    } catch { }
  }

"scanned $root, {0} overlong line(s)" -f $rows.Count | Set-Content $out -Encoding UTF8
$rows | Sort-Object Chars -Descending | Format-Table -AutoSize | Out-String -Width 200 | Add-Content $out -Encoding UTF8
Write-Output ("DONE {0} -> {1}" -f $rows.Count, $out)
