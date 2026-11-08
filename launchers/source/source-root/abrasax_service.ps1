# ============================================================================
# ABRASAX AI CORE — Guardian Service Script
# PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618033988749895
#
# Non-destructive system-level guardian. Every 30s:
#   1. Ensures the CRON_MASTER autonomous build loop is running (restarts if dead)
#   2. Probes LM Studio (:1234) and logs state (restart handled by resilience watchdog)
#   3. Writes heartbeat + service log
# Never kills processes. Never toggles guardrails.
# ============================================================================
param(
    [switch]$Once   # single supervision pass (scheduled-task mode); default = resident loop
)
$ErrorActionPreference = "Continue"

# Resolve the repo root robustly: env override, else the folder containing this
# script when CRON_MASTER.bat sits next to it (root-copy layout), else its parent
# (scripts\ layout). Fixes the root-copy bug where "parent of repo root" = Desktop.
$root = if ($env:ABRASAX_ROOT) { $env:ABRASAX_ROOT }
        elseif (Test-Path (Join-Path $PSScriptRoot 'CRON_MASTER.bat')) { $PSScriptRoot }
        else { Split-Path -Parent $PSScriptRoot }
$logDir = Join-Path $root "logs"
$log = Join-Path $logDir "service_watchdog.log"
$HEX = "4f5349524953424c58434b"
$LM_URL = "http://127.0.0.1:1234/v1/models"

$null = New-Item -ItemType Directory -Force -Path $logDir

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $entry = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Msg
    Add-Content -Path $log -Value $entry -Encoding utf8
}

Write-Log "=== ABRASAX AI CORE GUARDIAN START ==="
Write-Log "HEX: $HEX | Root: $root"
Write-Log "Guardian loop armed (interval 30s)"

$heartbeatTick = (Get-Date).AddMinutes(-6)  # force first heartbeat soon

# ── Single-pass mode (for Task Scheduler) ──────────────────────────────
if ($Once) {
    $loopAlive = $false
    try {
        $loopProcs = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'CRON_MASTER' }
        $loopAlive = ($null -ne $loopProcs)
    }
    catch { }
    if (-not $loopAlive) {
        Write-Log "CRON_MASTER loop not running — launching" "WARN"
        try {
            Start-Process -FilePath "cmd.exe" -ArgumentList '/c', "`"$root\CRON_MASTER.bat`"" `
                -WorkingDirectory $root -WindowStyle Hidden
            Write-Log "CRON_MASTER launched"
        }
        catch {
            Write-Log "CRON_MASTER launch failed: $($_.Exception.Message)" "ERROR"
        }
    }
    try {
        $resp = Invoke-WebRequest -Uri $LM_URL -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        $llmState = if ($resp.StatusCode -eq 200) { "UP" } else { "DEGRADED ($($resp.StatusCode))" }
    }
    catch { $llmState = "DOWN" }

    # 2b. Compute edit: pin loop workers to cores 4-15 (0xFFF0), leaving
    #     cores 0-3 free for the OS + LM Studio/LLM inference.
    try {
        $workers = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'llm_omega_build|local_nexus|orb_overlay' }
        foreach ($w in $workers) {
            $proc = Get-Process -Id $w.ProcessId -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessorAffinity -ne 0xFFF0) {
                $proc.ProcessorAffinity = 0xFFF0
                Write-Log "pinned worker PID $($w.ProcessId) -> cores 4-15"
            }
        }
    }
    catch { Write-Log "worker pinning: $($_.Exception.Message)" "WARN" }

    Write-Log "PASS: loop=$loopAlive llm=$llmState"
    exit 0
}

while ($true) {
    # 0. per-tick trace (added 2026-10-03 to localize silent-stall reports)
    Write-Log "TICK begin"
    # 1. Build loop (CRON_MASTER) supervision
    $loopAlive = $false
    try {
        $loopProcs = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'CRON_MASTER' }
        $loopAlive = ($null -ne $loopProcs)
    }
    catch { }
    Write-Log "TICK check done loopAlive=$loopAlive"
    if (-not $loopAlive) {
        Write-Log "CRON_MASTER loop not running - launching" "WARN"
        try {
            Start-Process -FilePath "cmd.exe" -ArgumentList '/c', "`"$root\CRON_MASTER.bat`"" `
                -WorkingDirectory $root -WindowStyle Hidden
            Write-Log "CRON_MASTER launched"
        }
        catch {
            Write-Log "CRON_MASTER launch failed: $($_.Exception.Message)" "ERROR"
        }
    }

    # 2. LM Studio probe (log only; restart duty belongs to resilience watchdog)
    try {
        $resp = Invoke-WebRequest -Uri $LM_URL -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $llmState = "UP" } else { $llmState = "DEGRADED ($($resp.StatusCode))" }
    }
    catch {
        $llmState = "DOWN"
    }

    # 3. Heartbeat every 5 minutes (log only; ABRASAX_HEARTBEAT.json owned by tiered_log)
    if ((Get-Date) -ge $heartbeatTick) {
        Write-Log "HEARTBEAT: loop=$loopAlive llm=$llmState"
        $heartbeatTick = (Get-Date).AddMinutes(5)
    }

    Start-Sleep -Seconds 30
}
