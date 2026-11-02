param(
    [Parameter(Mandatory=$true)][string]$Tag,
    [string]$Video = "G:\SORTED_MEDIA\Videos\05_Huge_Over_5GB\yoga-class-premium-seating_2160p.mp4",
    [int]$Seconds = 30,
    [string]$Vout = "",
    [string]$Filters = "KEEP",
    [string]$HwDec = "d3d11va",
    [switch]$NoUI
)
# ABRASAX VLC bench v3 — NORMAL VLC WINDOW (qt) unless -NoUI. Wall-clock kill, light sampling.
$ErrorActionPreference = "Continue"
$vlc = "C:\Program Files\VideoLAN\VLC\vlc.exe"
$outDir = Join-Path $env:TEMP "vlc_bench"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$log = Join-Path $outDir "$Tag.log"
if (Test-Path $log) { Remove-Item $log -Force }
$a = @("--file-logging","--logfile=$log","--logmode=text","--log-verbose=2","--no-video-title-show")
if ($NoUI) { $a = @("-I","dummy") + $a }
if ($Vout -ne "") { $a += "--vout=$Vout" }
if ($Filters -ne "KEEP") { $a += "--video-filter=$Filters" }
if ($HwDec -ne "KEEP") { $a += "--avcodec-hw=$HwDec" }
$a += "--started-from-file"; $a += $Video
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$proc = Start-Process -FilePath $vlc -ArgumentList $a -PassThru
$samples = @()
foreach ($t in @(10, 20, $Seconds)) {
    while ($sw.Elapsed.TotalSeconds -lt $t) { Start-Sleep -Milliseconds 400 }
    $pr = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $pr) { $samples += [pscustomobject]@{ t=$t; state="gone" }; continue }
    $nv = ((nvidia-smi --query-gpu=utilization.gpu,utilization.decoder --format=csv,noheader 2>$null) -join "").Trim()
    $samples += [pscustomobject]@{ t=$t; cpu_s=[math]::Round($pr.CPU,1); ws_mb=[math]::Round($pr.WorkingSet64/1MB); nv=$nv }
}
$wall = [math]::Round($sw.Elapsed.TotalSeconds,1)
$alive = -not $proc.HasExited
if ($alive) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 800
$txt = Get-Content $log -ErrorAction SilentlyContinue
$last300 = if ($txt.Count -gt 300) { $txt[($txt.Count-300)..($txt.Count-1)] } else { $txt }
$res = [ordered]@{
    tag            = $Tag
    ui             = if ($NoUI) { "dummy" } else { "qt" }
    vout_arg       = if ($Vout) { $Vout } else { "(vlcrc)" }
    filters        = $Filters
    wall_s         = $wall
    alive_at_kill  = $alive
    late_total     = ($txt | Select-String "picture is too late" -SimpleMatch).Count
    late_last300   = ($last300 | Select-String "picture is too late" -SimpleMatch).Count
    late_per_s     = if ($wall -gt 0) { [math]::Round((($txt | Select-String "picture is too late" -SimpleMatch).Count)/$wall,1) } else { 0 }
    dropped_total  = ($txt | Select-String "buffer too late" -SimpleMatch).Count
    converter_err  = ($txt | Select-String "Failed to create video converter" -SimpleMatch).Count
    decoder        = (($txt | Select-String "Using D3D11VA" -SimpleMatch | Select-Object -First 1).Line)
    voutused       = (($txt | Select-String "using vout display module" -SimpleMatch | Select-Object -First 1).Line)
    decwait        = (($txt | Select-String "Decoder wait done" -SimpleMatch | Select-Object -First 1).Line)
    samples        = $samples
}
$res | ConvertTo-Json -Depth 4
