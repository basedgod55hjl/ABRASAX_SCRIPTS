<#
.SYNOPSIS
    ABRASAX weekly disk cleanup - SAFE subset only.

.DESCRIPTION
    Runs, in this fixed order, and logs everything to C:\ABRASAX\LOGS\weekly-cleanup.log:

      1. Package caches:      python -m pip cache purge
                             uv cache clean
                             npm cache clean --force
         (each failure is logged and ignored - a missing tool is not an error)

      2. Temp directories:    %LOCALAPPDATA%\Temp\*      (locked files skipped)
                             C:\Windows\Temp\*          (only when elevated)

      3. Log rotation:        python SCRIPTS\automation\rotate_logs.py --apply
         rotate_logs.py is dry-run by default; this script passes --apply. It gzips
         logs older than 7 days to J:\ABRASAX-ARCHIVE\logs, verifies SHA-256, and
         only then removes the source. If J: is unavailable it aborts on its own.

      4. Report:              C: free space before/after, delta, and a warning when
                             free space is below -MinFreeGB (default 10 GB).
                             Nothing else is deleted to chase the threshold.

    NEVER TOUCHED (guarded in code, see $script:ProtectedFragments):
      models / GGUF, any venv, pagefile.sys, hiberfil.sys, media, personal files,
      %LOCALAPPDATA%\Yarn\Cache (already purged), .cache\abrasax7d, .lmstudio.
      Deletion is bounded to the two temp roots by Assert-UnderRoot; no path outside
      them can be removed even if enumeration returns something unexpected.

.PARAMETER DryRun
    Measure and log only. Nothing is deleted or rotated.

.PARAMETER MinFreeGB
    Warn when C: free space after the run is below this value. Default 10.

.PARAMETER LogPath
    Log file. Default C:\ABRASAX\LOGS\weekly-cleanup.log.

.NOTES
    Scheduled task : ABRASAX-Weekly-Cleanup  (Sunday 03:30, current user, no stored
                     password, StartWhenAvailable, no execution time limit)
    Exit codes     : 0 = run completed (locked files are normal, not a failure)
                     1 = fatal (log file unwritable)
    PowerShell     : Windows PowerShell 5.1 compatible.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Console,
    [double]$MinFreeGB = 10,
    [string]$LogPath = 'C:\ABRASAX\LOGS\weekly-cleanup.log'
)

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$script:Root        = 'C:\ABRASAX'
$script:VenvPython  = Join-Path $script:Root 'PYTHON\.venv_gui\Scripts\python.exe'
$script:Py311       = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
$script:UvExe       = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\Scripts\uv.exe'
$script:NodeExe     = 'C:\Program Files\nodejs\node.exe'
$script:NpmCmd      = 'C:\Program Files\nodejs\npm.cmd'
$script:RotateLogs  = Join-Path $script:Root 'SCRIPTS\automation\rotate_logs.py'

# Any path containing one of these fragments is refused, whatever the caller asks.
$script:ProtectedFragments = @(
    '\Yarn\Cache',
    '\.cache\abrasax7d',
    '\.lmstudio',
    '\pagefile.sys',
    '\hiberfil.sys',
    '\MODELS\',
    '\SEEDS\',
    '\pyvenv.cfg'
)

# ---------------------------------------------------------------- logging -----

$logDir = Split-Path -Parent $LogPath
if (-not (Test-Path -LiteralPath $logDir)) {
    try { New-Item -ItemType Directory -Path $logDir -Force | Out-Null } catch { }
}

# One append handle for the whole run. No Write-Host: under Task Scheduler with
# -WindowStyle Hidden there is no interactive console and a console write can block
# the process forever (observed: the run hung on its second log line). Use -Console
# for an interactive tail in a normal terminal window.
try {
    $fs = [System.IO.File]::Open($LogPath, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write,
                                 [System.IO.FileShare]::ReadWrite)
    $script:LogWriter = New-Object System.IO.StreamWriter($fs, (New-Object System.Text.UTF8Encoding($false)))
    $script:LogWriter.AutoFlush = $true
} catch {
    Write-Error "cannot open log file ${LogPath}: $($_.Exception.Message)"
    exit 1
}

function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet('INFO', 'OK', 'WARN', 'ERROR', 'STEP')][string]$Level = 'INFO'
    )
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try { $script:LogWriter.WriteLine($line) } catch { }
    if ($Console) {
        try { [Console]::Out.WriteLine($line) } catch { }
    }
}

function Close-Log {
    try { $script:LogWriter.Flush(); $script:LogWriter.Dispose() } catch { }
}

function Format-Bytes {
    param([double]$Bytes)
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N1} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N0} KB' -f ($Bytes / 1KB)) }
    return ('{0:N0} B' -f $Bytes)
}

# ---------------------------------------------------------------- helpers -----

function Resolve-Exe {
    param([string[]]$Candidates, [string]$Name)
    foreach ($c in $Candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return $null
}

function Get-CFree {
    try {
        $d = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction Stop
        return [pscustomobject]@{
            FreeGB  = [math]::Round($d.FreeSpace / 1GB, 2)
            TotalGB = [math]::Round($d.Size / 1GB, 2)
            FreeBytes = [double]$d.FreeSpace
        }
    } catch {
        $dr = Get-PSDrive -Name C -ErrorAction SilentlyContinue
        if ($dr) {
            return [pscustomobject]@{
                FreeGB    = [math]::Round($dr.Free / 1GB, 2)
                TotalGB   = [math]::Round(($dr.Used + $dr.Free) / 1GB, 2)
                FreeBytes = [double]$dr.Free
            }
        }
        return $null
    }
}

function Test-ProtectedPath {
    param([string]$Path)
    foreach ($f in $script:ProtectedFragments) {
        if ($Path.IndexOf($f, [StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    }
    return $false
}

function Assert-UnderRoot {
    param([string]$Path, [string]$Root)
    $r = $Root.TrimEnd('\')
    if (-not $Path.StartsWith($r + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "refused (not under $r): $Path"
    }
    if ($Path.TrimEnd('\') -ieq $r) {
        throw "refused (is the root itself): $Path"
    }
    if (Test-ProtectedPath $Path) {
        throw "refused (protected path): $Path"
    }
}

function Get-PathBytes {
    param([System.IO.FileSystemInfo]$Item)
    try {
        if ($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { return [double]0 }
    } catch { return [double]0 }

    if ($Item -is [System.IO.FileInfo]) { return [double]$Item.Length }

    $sum = [double]0
    try {
        $files = [System.IO.Directory]::EnumerateFiles($Item.FullName, '*', [System.IO.SearchOption]::AllDirectories)
        foreach ($f in $files) {
            try { $sum += (New-Object System.IO.FileInfo($f)).Length } catch { }
        }
    } catch {
        # access denied somewhere in the tree: the partial sum is still useful
    }
    return $sum
}

function Invoke-Tool {
    param(
        [string]$Exe,
        [string[]]$CmdArgs,
        [string]$Label,
        [int]$TimeoutSec = 180,
        [int]$MaxChars = 400
    )
    if (-not $Exe) {
        Write-Log "$Label - tool not found, skipped" 'WARN'
        return [pscustomobject]@{ Code = $null; Output = '' }
    }

    $argLine = ($CmdArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '

    Write-Log "$Label - $Exe $argLine (timeout ${TimeoutSec}s)"

    # Run through cmd.exe with output redirected to a FILE, never a PowerShell pipe.
    # Two observed failures this avoids:
    #   1. '& exe | Out-String' never returns: the venv python.exe is a launcher that
    #      re-execs the real interpreter, and the pipe stays open (hung twice).
    #   2. Redirecting through .NET streams leaves a multi-minute tail after a kill.
    # The wait is bounded; on timeout the whole tree is killed. Exit code is cmd's,
    # which forwards the child's, and is read from the .NET Process object.
    $outFile = Join-Path ([System.IO.Path]::GetTempPath()) ('weekly-cleanup-' + [guid]::NewGuid().ToString('N') + '.log')
    $cmdLine = '/d /c ""' + $Exe + '" ' + $argLine + ' > "' + $outFile + '" 2>&1"'

    $code = $null
    $text = ''
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName         = $env:ComSpec
    $psi.Arguments        = $cmdLine
    $psi.UseShellExecute  = $false
    $psi.CreateNoWindow   = $true
    $psi.WorkingDirectory = $script:Root

    try {
        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $psi
        $null = $p.Start()
        if ($p.WaitForExit($TimeoutSec * 1000)) {
            $code = $p.ExitCode
        } else {
            Write-Log "$Label - timed out after ${TimeoutSec}s, killing tree pid=$($p.Id)" 'WARN'
            & taskkill.exe /T /F /PID $p.Id 2>&1 | Out-Null
            $code = 'timeout'
        }
    } catch {
        Write-Log "$Label - could not run (ignored): $($_.Exception.Message)" 'WARN'
    }

    if (Test-Path -LiteralPath $outFile) {
        try { $text = (Get-Content -LiteralPath $outFile -Raw -ErrorAction Stop) -replace '\s+', ' ' } catch { }
        Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue
    }

    $text = $text.Trim()
    $raw = $text
    if ($text.Length -gt $MaxChars) { $text = $text.Substring(0, $MaxChars) + '...' }

    if ($code -eq 0) {
        Write-Log "$Label - exit 0$(if ($text) { ": $text" })" 'OK'
    } elseif ($code -eq 'timeout') {
        Write-Log "$Label - killed after timeout (ignored)" 'WARN'
    } else {
        Write-Log "$Label - exit $code (ignored): $text" 'WARN'
    }

    return [pscustomobject]@{ Code = $code; Output = $raw }
}

function Clear-TempRoot {
    param(
        [string]$Path,
        [string]$Label,
        [switch]$RequiresElevation,
        [bool]$Elevated,
        [switch]$DryRun
    )

    Write-Log "--- $Label : $Path" 'STEP'

    if ($RequiresElevation -and -not $Elevated) {
        Write-Log "$Label - skipped: requires elevation (not running as Administrator)" 'WARN'
        return [pscustomobject]@{ Label = $Label; Deleted = 0; Locked = 0; Skipped = 0; Bytes = [double]0 }
    }
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Log "$Label - skipped: path does not exist" 'WARN'
        return [pscustomobject]@{ Label = $Label; Deleted = 0; Locked = 0; Skipped = 0; Bytes = [double]0 }
    }

    $root = (Resolve-Path -LiteralPath $Path).Path.TrimEnd('\')
    $deleted = 0; $locked = 0; $skipped = 0; $bytes = [double]0; $considered = 0
    $failSamples = New-Object System.Collections.Generic.List[string]
    $bigItems    = New-Object System.Collections.Generic.List[object]

    $items = @(Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue)
    Write-Log "$Label - $($items.Count) top-level entries to consider"

    foreach ($it in $items) {
        $full = $it.FullName
        try { Assert-UnderRoot -Path $full -Root $root }
        catch {
            $skipped++
            Write-Log "$Label - $($_.Exception.Message)" 'WARN'
            continue
        }

        try {
            if ($it.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                # Never recurse into a junction/symlink: Remove-Item -Recurse on a reparse
                # point can delete the *target*. Leave it alone.
                $skipped++
                Write-Log "$Label - skipped reparse point: $full" 'WARN'
                continue
            }
        } catch { }

        $sz = Get-PathBytes -Item $it
        $bigItems.Add([pscustomobject]@{ Path = $full; Bytes = $sz })

        if ($DryRun) {
            $considered++
            $bytes += $sz
            continue
        }

        try {
            Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
            $deleted++
            $bytes += $sz
        } catch {
            $locked++
            if ($failSamples.Count -lt 5) {
                $failSamples.Add("$full -> $($_.Exception.Message)")
            }
        }
    }

    $verb = if ($DryRun) { 'would delete' } else { 'deleted' }
    $count = if ($DryRun) { $considered } else { $deleted }
    Write-Log ("{0} - {1} {2} item(s), {3}; locked/in use: {4}; skipped: {5}" -f `
            $Label, $verb, $count, (Format-Bytes $bytes), $locked, $skipped) 'OK'

    if ($failSamples.Count -gt 0) {
        foreach ($s in $failSamples) { Write-Log "$Label - locked sample: $s" 'INFO' }
    }

    $top = $bigItems | Sort-Object Bytes -Descending | Select-Object -First 5
    foreach ($t in $top) {
        if ($t.Bytes -ge 1MB) {
            Write-Log ("{0} - large entry: {1} = {2}" -f $Label, $t.Path, (Format-Bytes $t.Bytes))
        }
    }

    return [pscustomobject]@{ Label = $Label; Deleted = $deleted; Locked = $locked; Skipped = $skipped; Bytes = $bytes }
}

# ---------------------------------------------------------------- main --------

$started   = Get-Date
$elevated  = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
                [Security.Principal.WindowsBuiltInRole]::Administrator)
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Log ('=' * 72)
Write-Log ("ABRASAX weekly cleanup - start (dry-run={0})" -f [bool]$DryRun) 'STEP'
Write-Log "user=$identity elevated=$elevated host=$env:COMPUTERNAME pid=$PID"
Write-Log "script=$PSCommandPath log=$LogPath"

$before = Get-CFree
if ($before) {
    Write-Log ("C: before - free {0:N2} GB of {1:N2} GB" -f $before.FreeGB, $before.TotalGB) 'INFO'
} else {
    Write-Log 'C: free space could not be read before the run' 'WARN'
}

# Step 1 - package caches -------------------------------------------------------
Write-Log '--- 1/4 package caches' 'STEP'
$pipPython = Resolve-Exe -Candidates @($script:VenvPython, $script:Py311) -Name 'python'
if ($DryRun) {
    Write-Log 'pip cache purge - dry-run, not executed' 'INFO'
    Write-Log 'uv cache clean - dry-run, not executed' 'INFO'
    Write-Log 'npm cache clean --force - dry-run, not executed' 'INFO'
} else {
    if ($pipPython) {
        Invoke-Tool -Exe $pipPython -CmdArgs @('-m', 'pip', 'cache', 'purge') -Label 'pip cache purge' -TimeoutSec 120 | Out-Null
    } else {
        Write-Log 'pip cache purge - no python interpreter found, skipped' 'WARN'
    }
    Invoke-Tool -Exe (Resolve-Exe -Candidates @($script:UvExe, (Join-Path $env:USERPROFILE '.local\bin\uv.exe')) -Name 'uv') `
                -CmdArgs @('cache', 'clean') -Label 'uv cache clean' -TimeoutSec 180 | Out-Null

    # npm is a .cmd shim; run the CLI through node.exe so no cmd.exe wrapper is involved.
    $nodeExe = Resolve-Exe -Candidates @($script:NodeExe, 'C:\Program Files\nodejs\node.exe') -Name 'node'
    $npmCli  = Join-Path (Split-Path -Parent $script:NodeExe) 'node_modules\npm\bin\npm-cli.js'
    if ($nodeExe -and (Test-Path -LiteralPath $npmCli)) {
        Invoke-Tool -Exe $nodeExe -CmdArgs @($npmCli, 'cache', 'clean', '--force') `
                    -Label 'npm cache clean --force' -TimeoutSec 300 | Out-Null
    } else {
        Invoke-Tool -Exe (Resolve-Exe -Candidates @($script:NpmCmd) -Name 'npm') `
                    -CmdArgs @('cache', 'clean', '--force') -Label 'npm cache clean --force' -TimeoutSec 300 | Out-Null
    }
}

# Step 2 - temp directories -----------------------------------------------------
Write-Log '--- 2/4 temp directories' 'STEP'
$r1 = Clear-TempRoot -Path (Join-Path $env:LOCALAPPDATA 'Temp') -Label 'user temp' -Elevated $elevated -DryRun:$DryRun
$r2 = Clear-TempRoot -Path 'C:\Windows\Temp' -Label 'windows temp' -RequiresElevation -Elevated $elevated -DryRun:$DryRun

# Step 3 - log rotation ---------------------------------------------------------
Write-Log '--- 3/4 log rotation (rotate_logs.py --apply)' 'STEP'
$rotateFreed = [double]0
$rotateOk = $null
if (Test-Path -LiteralPath $script:RotateLogs) {
    if (-not $pipPython) {
        Write-Log 'log rotation - no python interpreter found, skipped' 'WARN'
    } elseif ($DryRun) {
        $res = Invoke-Tool -Exe $pipPython -CmdArgs @($script:RotateLogs, '--json') `
                    -Label 'log rotation (dry-run)' -TimeoutSec 600 -MaxChars 2000
    } else {
        $res = Invoke-Tool -Exe $pipPython -CmdArgs @($script:RotateLogs, '--apply', '--json') `
                    -Label 'log rotation --apply' -TimeoutSec 900 -MaxChars 2000
        $rotateOk = $res.Code
        $compact = $res.Output
        $m = [regex]::Match($compact, '\{"mode".*\}')
        if ($m.Success) {
            try {
                $o = $m.Value | ConvertFrom-Json
                $rotateFreed = [double]$o.would_free_bytes
                Write-Log ("log rotation - mode={0} candidates={1} bytes={2} skipped={3} run_dir={4}" -f `
                        $o.mode, $o.candidates, $o.would_free_bytes, $o.skipped, $o.run_dir) 'OK'
            } catch {
                Write-Log "log rotation - output could not be parsed: $compact" 'WARN'
            }
        } else {
            Write-Log "log rotation - exit $rotateOk, output: $compact" 'WARN'
        }
        if ($rotateOk -ne 0) {
            Write-Log "log rotation - rotate_logs.py exited $rotateOk (archive drive J: missing or write failed); logs left in place" 'WARN'
        }
    }
} else {
    Write-Log "log rotation - $script:RotateLogs not found, skipped" 'WARN'
}

# Step 4 - report ---------------------------------------------------------------
Write-Log '--- 4/4 free space report' 'STEP'
$after = Get-CFree
$totalBytes = [double]$r1.Bytes + [double]$r2.Bytes
if (-not $DryRun) { $totalBytes += $rotateFreed }

if ($before -and $after) {
    $delta = $after.FreeGB - $before.FreeGB
    Write-Log ("C: after  - free {0:N2} GB of {1:N2} GB (delta {2:+0.00;-0.00;0.00} GB)" -f `
            $after.FreeGB, $after.TotalGB, $delta) 'OK'
    Write-Log ("freed by this run - temp {0} + rotated logs {1} = {2} reported; free-space delta {3:+0.00;-0.00;0.00} GB" -f `
            (Format-Bytes ([double]$r1.Bytes + [double]$r2.Bytes)), (Format-Bytes $rotateFreed), `
            (Format-Bytes $totalBytes), $delta) 'OK'
} else {
    Write-Log 'C: free space could not be read after the run' 'WARN'
}

if ($after -and $after.FreeGB -lt $MinFreeGB) {
    Write-Log ("WARNING: C: free space {0:N2} GB is below the {1:N2} GB threshold - nothing else was deleted; " -f $after.FreeGB, $MinFreeGB) 'WARN'
    Write-Log 'WARNING: review DOC/DISK-CLEAN/*.md and move (do not delete) archive candidates.' 'WARN'
} elseif ($after) {
    Write-Log ("C: free space {0:N2} GB is above the {1:N2} GB threshold" -f $after.FreeGB, $MinFreeGB) 'OK'
}

$elapsed = ((Get-Date) - $started).TotalSeconds
Write-Log ("ABRASAX weekly cleanup - done in {0:N1}s (dry-run={1})" -f $elapsed, [bool]$DryRun) 'STEP'
Write-Log ('=' * 72)
Close-Log

exit 0
