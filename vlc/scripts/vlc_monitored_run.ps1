$ErrorActionPreference = "Continue"
$vlc = "C:\Program Files\VideoLAN\VLC\vlc.exe"
$video = "G:\SORTED_MEDIA\Videos\05_Huge_Over_5GB\yoga-class-premium-seating_2160p.mp4"
$log = "$env:TEMP\vlc_bench\M_monitored.log"
if (Test-Path $log) { Remove-Item $log -Force }
"=== launching normal VLC window ==="
$v = Start-Process -FilePath $vlc -ArgumentList @("--file-logging","--logfile=$log","--logmode=text","--log-verbose=2","--no-video-title-show","--started-from-file",$video) -PassThru
Start-Sleep -Seconds 3
"=== starting vlc_monitor.ps1 (10 ticks x 5s) ==="
$mon = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File","C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\scripts\vlc_monitor.ps1","-IntervalSec","5","-Count","10") -PassThru -WindowStyle Hidden
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 62) {
    Start-Sleep -Milliseconds 500
    if ($sw.Elapsed.TotalSeconds -gt 30 -and -not $script:nv1) {
        $script:nv1 = $true
        "=== mid-run nvidia-smi: " + ((nvidia-smi --query-gpu=utilization.gpu,utilization.decoder,memory.used --format=csv,noheader 2>$null) -join "") + " ==="
    }
}
if (-not $v.HasExited) { Stop-Process -Id $v.Id -Force }
$script:nv1 = $false
$mon | Wait-Process -Timeout 25 -ErrorAction SilentlyContinue
if (-not $mon.HasExited) { Stop-Process -Id $mon.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
"---- monitor log tail ----"
Get-Content "$env:TEMP\vlc_monitor\vlc_monitor_log.txt" -Tail 15
"---- vlc summary ----"
$t = Get-Content $log -ErrorAction SilentlyContinue
"late_total: " + ($t | Select-String 'picture is too late' -SimpleMatch).Count
"might_late: " + ($t | Select-String 'might be displayed late' -SimpleMatch).Count
"dropped: " + ($t | Select-String 'buffer too late' -SimpleMatch).Count
"decoder: " + (($t | Select-String 'Using D3D11VA' -SimpleMatch | Select-Object -First 1).Line)
"vout: " + (($t | Select-String 'using vout display module' -SimpleMatch | Select-Object -First 1).Line)
"filter_errors: " + ($t | Select-String 'Unsupported chroma' -SimpleMatch).Count
