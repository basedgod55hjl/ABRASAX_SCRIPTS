#requires -Version 5.1
<#
  ABRASAX - rolling offload + verified reclaim.

  Runs forever (until stopped) doing what the one-shot scripts did:

    pass 1  offload_s25.ps1        pull whatever is new on the phone
    pass 2  reclaim_s25.ps1 -Apply delete only files whose SHA-256 is already
                                  recorded in the manifest

  Safe by construction: reclaim re-checks the hash of the local copy before it
  deletes anything on the phone, so a partial or failed pull is never trusted.

  Writes progress to LOGS/rolling.log and exits when the phone stops yielding
  new files (nothing left to move) or when told to.
#>
param(
  [string]$Serial = 'R5CY308WZVK',
  [string]$Dest   = 'J:\ABRASAX_OFFLOAD\S25_R5CY308WZVK',
  [int]$Cycles    = 0,          # 0 = until no new data
  [int]$SleepMin  = 5
)

$ErrorActionPreference = 'Continue'
$root = 'C:\ABRASAX'
$log  = Join-Path $root 'LOGS\rolling.log'

function Note($m) {
  $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
  Add-Content -LiteralPath $log -Value $line
  Write-Host $line
}

Note "rolling offload start (serial=$Serial dest=$Dest)"

$cycle = 0
while ($true) {
  $cycle++
  if ($Cycles -gt 0 -and $cycle -gt $Cycles) { Note "cycle limit reached"; break }

  $before = (Get-ChildItem $Dest -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum

  # --- pass 1: pull ---
  try {
    & (Join-Path $root 'SCRIPTS\offload\offload_s25.ps1') -Serial $Serial -Dest $Dest 2>&1 |
      ForEach-Object { if ($_ -match 'offload|done') { Note "pull: $_" } }
  } catch {
    Note "pull error: $($_.Exception.Message)"
  }

  $after = (Get-ChildItem $Dest -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
  $grew  = [math]::Round(($after - $before) / 1GB, 3)
  Note ("cycle {0}: pulled {1} GB (total {2} GB)" -f $cycle, $grew, [math]::Round($after/1GB,2))

  # --- pass 2: verified delete ---
  try {
    $out = & (Join-Path $root 'SCRIPTS\offload\reclaim_s25.ps1') -Serial $Serial -Dest $Dest -Apply 2>&1
    $tail = ($out | Select-Object -Last 8) -join ' '
    Note "reclaim: $tail"
  } catch {
    Note "reclaim error: $($_.Exception.Message)"
  }

  $df = & 'C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe' -s $Serial shell 'df -k /data | tail -1'  # DEAD PATH (sirch): no adb.exe on this host
  Note "phone: $df"

  # Nothing moved and nothing was reclaimed -> the job is done.
  if ($grew -le 0.01 -and $Cycles -eq 0) {
    Note "no new data in cycle $cycle; stopping"
    break
  }

  Start-Sleep -Seconds ($SleepMin * 60)
}

Note "rolling offload finished after $cycle cycle(s)"
