Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class Win32Move {
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string w);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int h, bool r);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder t, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint id);
    [DllImport("user32.dll")] public static extern IntPtr GetDesktopWindow();
}
"@

# Detect monitors
Add-Type -AssemblyName System.Windows.Forms
$screens = [System.Windows.Forms.Screen]::AllScreens

Write-Host "Monitors:"
for($i=0; $i -lt $screens.Length; $i++) {
    $b = $screens[$i].Bounds
    Write-Host "  $($i+1): $($b.Width)x$($b.Height) at ($($b.X),$($b.Y)) - $($screens[$i].DeviceName)"
}

# Use the SECOND monitor (Dell) - assume it's Display2 or the wide one
# If second monitor is 1536x864 at (1536,0) - use that
$targetMonitor = $null
foreach($s in $screens) {
    if ($s.Bounds.X -gt 0 -or $s.Bounds.Y -gt 0) {
        if ($targetMonitor -eq $null -or $s.Bounds.Width -gt $targetMonitor.Bounds.Width) {
            $targetMonitor = $s
        }
    }
}
if ($targetMonitor -eq $null) { $targetMonitor = $screens[$screens.Length-1] }

$mx = $targetMonitor.Bounds.X
$my = $targetMonitor.Bounds.Y
$mw = $targetMonitor.Bounds.Width
$mh = $targetMonitor.Bounds.Height

Write-Host ""
Write-Host "Target monitor: $($mw)x$($mh) at ($mx,$my)"
Write-Host ""

# Find all pi/cmd windows with pi running
$piPids = @()
$piWindows = @()
$callback = {
    param($hwnd, $lparam)
    $sb = New-Object System.Text.StringBuilder 256
    [Win32Move]::GetWindowText($hwnd, $sb, 256)
    $title = $sb.ToString()
    if ($title -match "PI|pi|node|agent|Administrator") {
        $pid = 0
        [Win32Move]::GetWindowThreadProcessId($hwnd, [ref]$pid)
        if ($pid -gt 0 -and $title -ne "" -and $title -ne "Default IME") {
            Write-Host "  PID:$pid -> $title"
            $piWindows += @{HWND=$hwnd; PID=$pid; Title=$title}
        }
    }
    return $true
}

$enum = [Win32Move].GetMethods() | Where { $_.Name -eq "EnumWindows" }
if (-not $enum) {
    # Manual approach: find specific windows
    $procs = Get-Process -Name "cmd","node" -ErrorAction SilentlyContinue | Sort-Object Id
    Write-Host "Found $($procs.Count) cmd/node processes:"
    $idx = 0
    foreach($p in $procs) {
        if ($p.MainWindowTitle -ne "") {
            Write-Host "  $($p.Id): $($p.MainWindowTitle)"
            if ($idx -lt 4) {
                $h = $p.MainWindowHandle
                # Grid: 2x2
                $col = $idx % 2
                $row = [Math]::Floor($idx / 2)
                $wx = $mx + $col * ($mw / 2)
                $wy = $my + $row * ($mh / 2)
                $ww = $mw / 2
                $wh = $mh / 2
                [Win32Move]::MoveWindow($h, [int]$wx, [int]$wy, [int]$ww, [int]$wh, $true)
                [Win32Move]::ShowWindow($h, 1)
                Write-Host "    -> Moved to ($wx,$wy) size $($ww)x$($wh)"
                $idx++
            }
        }
    }
}
