# find_long_lines.ps1 - which home-dir text files break findstr.
#
# FINDSTR: "Line 62 is too long" is not a findstr bug: findstr cannot search a
# file whose line exceeds ~8191 characters. One minified JSON or a log written
# without newlines is enough, and it kills the whole search that touched it.
#
#   powershell -ExecutionPolicy Bypass -File SCRIPTS\find_long_lines.ps1

$root  = 'C:\Users\lucar'
$limit = 3000
$rows  = @()

Get-ChildItem $root -File -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -in '.txt', '.log', '.md', '.json', '.jsonl' } |
  ForEach-Object {
    $f = $_
    try {
      $reader = [System.IO.File]::OpenText($f.FullName)
      $n = 0
      while ($null -ne ($line = $reader.ReadLine())) {
        $n++
        if ($line.Length -gt $limit) {
          $rows += [pscustomobject]@{
            File    = $f.Name
            Line    = $n
            Chars   = $line.Length
            Preview = $line.Substring(0, [Math]::Min(60, $line.Length))
          }
        }
      }
      $reader.Close()
    } catch {
      $rows += [pscustomobject]@{ File = $f.Name; Line = 0; Chars = -1; Preview = $_.Exception.Message }
    }
  }

if ($rows.Count -gt 0) {
  $rows | Sort-Object Chars -Descending | Format-Table -AutoSize
  $files = ($rows | Select-Object -ExpandProperty File -Unique).Count
  Write-Output ("{0} overlong line(s) across {1} file(s); findstr fails on any of them." -f $rows.Count, $files)
} else {
  Write-Output ("no line over {0} chars in {1}" -f $limit, $root)
}
