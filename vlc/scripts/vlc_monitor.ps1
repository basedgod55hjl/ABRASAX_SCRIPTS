# ============================================================
#  VLC DEBUG MONITOR -- screenshot + brightness + decode telemetry
#  PRIMAL_HEX: 4f5349524953424c58434b | ABRASAX 2026-10-03
#  Usage: powershell -NoProfile -File vlc_monitor.ps1 [-IntervalSec 5] [-Count 0]
#  -Count 0 = run until VLC exits. Log + shots land in -OutDir.
#  Keep the VLC window VISIBLE (captures actual screen pixels of its rect).
# ============================================================
param(
    [int]$IntervalSec = 5,
    [int]$Count = 0,
    [string]$OutDir = "$env:TEMP\vlc_monitor"
)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class VlcMon {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    public struct RECT { public int L, T, R, B; }
}
"@

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$log = Join-Path $OutDir "vlc_monitor_log.txt"

function Write-Log([string]$msg) {
    $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $msg
    Add-Content -Path $log -Value $line
    Write-Output $line
}

Write-Log "=== VLC DEBUG MONITOR START (interval=${IntervalSec}s, count=$Count) ==="

$screen = [System.Windows.Forms.SystemInformation]::VirtualScreen
$tick = 0
while ($true) {
    $tick++
    $v = Get-Process vlc -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
    if (-not $v) { Write-Log "EXIT: no VLC process found (was running before? monitor stopping)"; break }
    $v.Refresh()
    $title = $v.MainWindowTitle
    if ($title.Length -gt 80) { $title = $title.Substring(0, 77) + "..." }
    $resp = $v.Responding
    $ram = [math]::Round($v.WorkingSet64 / 1MB)
    $bright = "n/a"
    $shot = Join-Path $OutDir "vlc_latest.png"

    if ($v.MainWindowHandle -ne 0) {
        try {
            $r = New-Object VlcMon+RECT
            [void][VlcMon]::GetWindowRect($v.MainWindowHandle, [ref]$r)
            $x = [Math]::Max(0, $r.L - $screen.X + 20)
            $y = [Math]::Max(0, $r.T - $screen.Y + 70)
            $w = [Math]::Max(120, $r.R - $r.L - 40)
            $h = [Math]::Max(120, $r.B - $r.T - 100)
            $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($screen.X, $screen.Y, 0, 0, $bmp.Size)
            $g.Dispose()
            $rect = New-Object System.Drawing.Rectangle($x, $y, $w, $h)
            $crop = $bmp.Clone($rect, $bmp.PixelFormat)
            $crop.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
            $crop.Dispose()
            $sum = 0; $n = 0
            for ($px = $x; $px -lt ($x + $w); $px += 40) {
                for ($py = $y; $py -lt ($y + $h); $py += 40) {
                    $c = $bmp.GetPixel($px, $py); $sum += ($c.R + $c.G + $c.B) / 3; $n++
                }
            }
            $bmp.Dispose()
            if ($n -gt 0) { $bright = [Math]::Round($sum / $n, 1) }
        } catch {
            $bright = "err"
        }
    }

    $dec = ""
    try { $dec = (nvidia-smi --query-gpu=utilization.decoder --format=csv,noheader 2>$null | Select-Object -First 1) } catch {}
    $gpu = ""
    try { $gpu = (nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader 2>$null | Select-Object -First 1) } catch {}

    $flag = ""
    if ($bright -ne "n/a" -and $bright -ne "err" -and [double]$bright -lt 5) { $flag = "  <<< BLACK SCREEN?" }
    if (-not $resp) { $flag += "  <<< NOT RESPONDING" }

    Write-Log ("tick $tick  pid=$($v.Id)  ram=${ram}MB  resp=$resp  gpu=[$gpu]  dec=[$dec]  brightness=$bright  file=$title$flag")

    if ($Count -gt 0 -and $tick -ge $Count) { break }
    Start-Sleep -Seconds $IntervalSec
}

Write-Log "=== MONITOR STOP (ticks=$tick) -- log: $log shots: $OutDir ==="
