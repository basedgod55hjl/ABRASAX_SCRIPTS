# find_line62.ps1 - locate the file whose 62nd line breaks findstr.
#
# findstr names the line it choked on. The top-level profile scan found long lines
# only at lines 1, 3 and 19, so the offender lives elsewhere. This checks each
# candidate directory's *.txt/*.log/*.md and reports the longest line WITH its
# line number, flagging anything near findstr's ~8191 ceiling.

$dirs = @(
  'C:\abrasax',
  'C:\vlc-build',
  'C:\Users\lucar\Downloads',
  'C:\Users\lucar\Documents',
  'C:\Users\lucar\Desktop'
)

$rows = @()
foreach ($d in $dirs) {
  if (-not (Test-Path $d)) { continue }
  Get-ChildItem $d -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.txt', '.log', '.md' -and $_.Length -lt 50MB } |
    ForEach-Object {
      $f = $_
      try {
        $max = 0; $at = 0; $n = 0
        $rd = [System.IO.File]::OpenText($f.FullName)
        while ($null -ne ($line = $rd.ReadLine())) {
          $n++
          if ($line.Length -gt $max) { $max = $line.Length; $at = $n }
        }
        $rd.Close()
        if ($max -gt 8000) {
          $rows += [pscustomobject]@{
            Dir = $d; File = $f.Name; Lines = $n
            LongestAtLine = $at; Chars = $max
            LooksLike62 = ($at -eq 62)
          }
        }
      } catch { }
    }
}

if ($rows.Count -gt 0) {
  $rows | Sort-Object Chars -Descending | Format-Table -AutoSize
  Write-Output ("`n{0} file(s) exceed 8000 chars on a line; offender-at-line-62: {1}" -f `
    $rows.Count, (($rows | Where-Object { $_.LooksLike62 }).File -join ', '))
} else {
  Write-Output "no file over 8000 chars/line in the checked directories"
}
