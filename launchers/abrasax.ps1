<#
.SYNOPSIS
  ABRASAX unified workflow launcher.

.DESCRIPTION
  One entry point for the whole stack. Safe and idempotent.

    .\abrasax.ps1 status            services + endpoints
    .\abrasax.ps1 start             bring the stack up (no duplicates)
    .\abrasax.ps1 stop              stop ABRASAX-owned processes only
    .\abrasax.ps1 restart           stop then start
    .\abrasax.ps1 verify            end-to-end truth check (exit 1 on failure)
    .\abrasax.ps1 world             Phase 1 world-model check (world/camera/sensors/UI)
    .\abrasax.ps1 verify -NoTests   skip the fast pytest subset
    .\abrasax.ps1 doctor            environment, deps, disk, RAM, ports, masked keys
    .\abrasax.ps1 logs              tail the service logs
    .\abrasax.ps1 paths             print resolved root and interpreters

  Root resolution: $env:ABRASAX_ROOT, else two levels above this script,
  else C:\abrasax.
#>
param(
    [Parameter(Position = 0)][string]$Command = 'status',
    [switch]$NoTests,
    [switch]$Quiet,
    [int]$Tail = 15
)

$ErrorActionPreference = 'Continue'

function Resolve-Root {
    if ($env:ABRASAX_ROOT -and (Test-Path (Join-Path $env:ABRASAX_ROOT 'abrasax'))) {
        return (Resolve-Path $env:ABRASAX_ROOT).Path
    }
    $candidate = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    if ($candidate -and (Test-Path (Join-Path $candidate 'abrasax'))) { return $candidate }
    return 'C:\abrasax'
}

$Root = Resolve-Root
$Py   = Join-Path $Root 'PYTHON\.venv_gui\Scripts\python.exe'
$Pyw  = Join-Path $Root 'PYTHON\.venv_gui\Scripts\pythonw.exe'
$Verify = Join-Path $Root 'SCRIPTS\automation\verify_stack.py'
$VerifyWorld = Join-Path $Root 'SCRIPTS\automation\verify_world.py'
$Stack  = Join-Path $Root 'SCRIPTS\launchers\start_abrasax_stack.ps1'

function Say([string]$Text, [string]$Color = 'Gray') {
    if (-not $Quiet) { Write-Host $Text -ForegroundColor $Color }
}
function Head([string]$Text) { Say ''; Say "== $Text ==" 'Cyan' }

function Test-Port([int]$Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $task = $client.ConnectAsync('127.0.0.1', $Port)
        $ok = $task.Wait(250)
        $client.Close()
        return ($ok -and $task.IsCompleted -and -not $task.IsFaulted)
    } catch { return $false }
}

function Show-Status {
    Head "stack status ($Root)"
    if (-not (Test-Path $Py)) { Say "python missing: $Py" 'Red'; return 1 }
    $json = & $Py -m abrasax services --json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) { Say 'service probe failed' 'Red'; return 1 }
    $rows = $json | ConvertFrom-Json
    $down = @()
    foreach ($r in $rows) {
        if ($null -eq $r.port) { continue }
        $state = if ($r.up) { 'UP' } else { 'down' }
        $lat = if ($null -ne $r.latency_ms) { ('{0,8:N2} ms' -f $r.latency_ms) } else { '       -' }
        $color = if ($r.up) { 'Green' } else { if ($r.optional) { 'DarkYellow' } else { 'Red' } }
        Say ("{0,-24} {1,5}  {2,-4} {3}" -f $r.id, $r.port, $state, $lat) $color
        if (-not $r.up -and -not $r.optional) { $down += $r.id }
    }
    Say ''
    foreach ($probe in @(
            @{ n = 'gateway /health'; u = 'http://127.0.0.1:9001/health' },
            @{ n = 'gateway /v1/agents'; u = 'http://127.0.0.1:9001/v1/agents' },
            @{ n = 'brain /state'; u = 'http://127.0.0.1:9626/state' },
            @{ n = 'UI /'; u = 'http://127.0.0.1:8090/' },
            @{ n = 'overlay /health'; u = 'http://127.0.0.1:9627/health' })) {
        try {
            $resp = Invoke-WebRequest -Uri $probe.u -TimeoutSec 12 -UseBasicParsing
            Say ("{0,-22} HTTP {1}" -f $probe.n, $resp.StatusCode) 'Green'
        } catch {
            Say ("{0,-22} FAIL {1}" -f $probe.n, $_.Exception.Message.Split([char]10)[0]) 'Red'
            $down += $probe.n
        }
    }
    if ($down.Count) { Say ("`nDOWN: " + ($down -join ', ')) 'Red'; return 1 }
    Say "`nall critical services up" 'Green'
    return 0
}

function Start-Stack {
    Head 'start stack'
    if (-not (Test-Path $Stack)) { Say "launcher missing: $Stack" 'Red'; return 1 }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Stack -Quiet:$Quiet | Out-Host
    return $LASTEXITCODE
}

$OwnedPatterns = @(
    'supervisor.py', 'ops_monitor.py', '-m abrasax buildloop', '-m abrasax gateway',
    '-m abrasax.brain serve', 'abraxas_cellbrain.py', 'abraxas_synaptic_server.py',
    'filetool.py', 'routerfail.py', 'node_lm_server', 'server.mjs',
    'codec_gateway', 'media-grabber', 'imgui_overlay.py', 'fb_server.exe',
    'abrasax_hud.py'
)

function Stop-Stack {
    Head 'stop ABRASAX-owned processes'
    $rootPattern = [regex]::Escape($Root)
    $stopped = 0
    $procs = Get-CimInstance Win32_Process | Where-Object {
        $proc = $_
        if (-not $proc.CommandLine -or $proc.CommandLine -notmatch $rootPattern) { return $false }
        foreach ($pattern in $OwnedPatterns) {
            if ($proc.CommandLine -like "*$pattern*") { return $true }
        }
        return $false
    }
    foreach ($p in $procs) {
        try {
            Say ("stop {0,-8} {1}" -f $p.ProcessId, ($p.CommandLine.Substring(0, [Math]::Min(110, $p.CommandLine.Length)))) 'Yellow'
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            $stopped++
        } catch { Say ("could not stop {0}: {1}" -f $p.ProcessId, $_.Exception.Message) 'Red' }
    }
    Say "stopped $stopped process(es)"
    return 0
}

function Invoke-Verify {
    Head 'end-to-end verification'
    if (-not (Test-Path $Verify)) { Say "verifier missing: $Verify" 'Red'; return 1 }
    $vargs = @($Verify)
    if (-not $NoTests) { $vargs += '--tests' }
    & $Py @vargs | Out-Host
    $stackRc = $LASTEXITCODE
    if (Test-Path $VerifyWorld) {
        Head 'Phase 1 world model'
        $wargs = @($VerifyWorld)
        if (-not $NoTests) { $wargs += '--tests' }
        & $Py @wargs | Out-Host
        $worldRc = $LASTEXITCODE
    } else {
        Say "world verifier missing: $VerifyWorld" 'Yellow'
        $worldRc = 0
    }
    if ($stackRc -ne 0) { return $stackRc }
    return $worldRc
}

function Invoke-WorldVerify {
    Head 'Phase 1 world model'
    if (-not (Test-Path $VerifyWorld)) { Say "verifier missing: $VerifyWorld" 'Red'; return 1 }
    $wargs = @($VerifyWorld)
    if (-not $NoTests) { $wargs += '--tests' }
    & $Py @wargs | Out-Host
    return $LASTEXITCODE
}

function Show-Doctor {
    Head 'doctor'
    $fail = 0
    Say ("root        $Root")
    Say ("python      $Py")
    if (Test-Path $Py) {
        $ver = & $Py --version 2>&1
        Say ("version     $ver") 'Green'
        # find_spec does not import the module, so this is fast even under load
        $deps = & $Py -c "import importlib.util as u; mods=['requests','numpy','flask','httpx','psutil','pytest']; have=[m for m in mods if u.find_spec(m)]; miss=[m for m in mods if m not in have]; print('have: ' + ' '.join(have)); print('missing: ' + (' '.join(miss) if miss else 'none'))" 2>&1
        foreach ($line in $deps) { Say ("deps        $line") 'Green' }
        $missingLine = ($deps | Where-Object { $_ -like 'missing:*' } | Select-Object -First 1)
        if ($missingLine -and $missingLine -notlike '*none*') { Say 'deps        optional modules missing (services do not require them)' 'Yellow' }
        & $Py -c "import abrasax; print('package    ', abrasax.__version__, abrasax.__file__)" 2>&1 | ForEach-Object { Say $_ 'Green' }
    } else { Say 'python      MISSING' 'Red'; $fail++ }

    $disk = Get-PSDrive C -ErrorAction SilentlyContinue
    if ($disk) {
        $free = [math]::Round($disk.Free / 1GB, 1)
        $color = if ($free -lt 5) { 'Red' } elseif ($free -lt 15) { 'Yellow' } else { 'Green' }
        Say ("disk C:     {0} GB free" -f $free) $color
    }
    $os = Get-CimInstance Win32_OperatingSystem
    $ramFree = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
    $ramTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
    $ramColor = if ($ramFree -lt 1) { 'Red' } elseif ($ramFree -lt 3) { 'Yellow' } else { 'Green' }
    Say ("ram         {0} GB free / {1} GB" -f $ramFree, $ramTotal) $ramColor
    Say ("commit      {0} GB" -f [math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1MB, 2))

    foreach ($port in 9001, 9626, 8090, 9624, 9625, 8777, 8765, 8766, 8795, 9782, 9700, 9627) {
        $ok = Test-Port $port
        $color = if ($ok) { 'Green' } else { 'Yellow' }
        Say ("port {0,-5} {1}" -f $port, $(if ($ok) { 'LISTEN' } else { 'closed' })) $color
    }

    $envFile = Join-Path $Root '.env'
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$') {
                $k = $Matches[1]; $v = $Matches[2].Trim('"').Trim("'")
                if ($k -match '(?i)(API_KEY$|_KEY$|_TOKEN$|SECRET|PASSWORD)' -and $v.Length -gt 0) {
                    $mask = $v.Substring(0, [Math]::Min(4, $v.Length)) + '...(' + $v.Length + ')'
                    Say ("env {0,-24} {1}" -f $k, $mask) 'DarkGray'
                }
            }
        }
    } else { Say "env         .env missing" 'Yellow' }

    foreach ($tool in 'cargo', 'node', 'dotnet', 'java', 'nvcc', 'cmake') {
        $cmd = Get-Command $tool -ErrorAction SilentlyContinue
        if ($cmd) { Say ("tool {0,-8} {1}" -f $tool, $cmd.Source) 'Green' }
        else { Say ("tool {0,-8} missing" -f $tool) 'DarkYellow' }
    }
    if ($fail) { Say "`ndoctor found $fail problem(s)" 'Red'; return 1 }
    Say "`ndoctor: ok" 'Green'
    return 0
}

function Show-Logs {
    Head "service logs (last $Tail lines)"
    $files = Get-ChildItem (Join-Path $Root 'LOGS\svc-*.log') -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime
    if (-not $files) { Say 'no svc-*.log files' 'Yellow'; return 0 }
    foreach ($f in $files) {
        Say ("`n--- {0}  ({1:yyyy-MM-dd HH:mm:ss}, {2} B) ---" -f $f.Name, $f.LastWriteTime, $f.Length) 'Cyan'
        Get-Content -LiteralPath $f.FullName -Tail $Tail -ErrorAction SilentlyContinue | Out-Host
    }
    return 0
}

switch ($Command.ToLower()) {
    'status'  { exit (Show-Status) }
    'start'   { exit (Start-Stack) }
    'stop'    { exit (Stop-Stack) }
    'restart' { Stop-Stack | Out-Null; Start-Sleep -Seconds 2; exit (Start-Stack) }
    'verify'  { exit (Invoke-Verify) }
    'world'   { exit (Invoke-WorldVerify) }
    'doctor'  { exit (Show-Doctor) }
    'logs'    { exit (Show-Logs) }
    'paths'   { Say "root=$Root"; Say "python=$Py"; Say "pythonw=$Pyw"; Say "verify=$Verify"; exit 0 }
    default {
        Say "unknown command: $Command" 'Red'
        Say 'use: status | start | stop | restart | verify | world | doctor | logs | paths' 'Yellow'
        exit 2
    }
}
