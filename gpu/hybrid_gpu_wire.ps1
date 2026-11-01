# hybrid_gpu_wire.ps1 — route DISPLAY RENDERING to the AMD iGPU while leaving the
# NVIDIA dGPU free for compute (CUDA kernels, NVENC, ffmpeg).
#
# WHY THIS IS THE ONLY LEVER
# VLC exposes --avcodec-hw={any,d3d11va,dxva2,none} with NO device/adapter index, and there is
# no --direct3d11-device option (only --directx-device, which belongs to the d3d9 vout). So a
# single VLC process cannot decode on one GPU and present on another; the adapter the whole
# process lands on is chosen by Windows through
#   HKCU\Software\Microsoft\DirectX\UserGpuPreferences
#     value name = FULL exe path, value = GpuPreference=<n>
#       n = 1 -> power saving / integrated (AMD Radeon Graphics)
#       n = 2 -> high performance (NVIDIA GeForce GTX 1660 Ti)
# Applies at next process launch; no reboot required.
#
# Usage:
#   hybrid_gpu_wire.ps1 -Show                     # report current routing
#   hybrid_gpu_wire.ps1 -App vlc -To amd          # VLC renders on the iGPU
#   hybrid_gpu_wire.ps1 -App vlc -To nvidia       # VLC renders on the dGPU
#   hybrid_gpu_wire.ps1 -App vlc -To auto         # remove the override
param(
    [ValidateSet('vlc','ffmpeg','msedge','chrome','steam','explorer')]
    [string]$App,
    [ValidateSet('amd','nvidia','auto')]
    [string]$To,
    [switch]$Show
)

$Key = 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'

$Paths = @{
    vlc      = 'C:\Program Files\VideoLAN\VLC\vlc.exe'
    ffmpeg   = "$env:LOCALAPPDATA\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe"
    msedge   = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    chrome   = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
    steam    = 'C:\Program Files (x86)\Steam\steam.exe'
    explorer = 'C:\Windows\explorer.exe'
}

function Show-Routing {
    Write-Host '=== Per-app GPU routing (HKCU\...\DirectX\UserGpuPreferences) ==='
    if (-not (Test-Path $Key)) { Write-Host '  (key not present)'; return }
    $props = (Get-ItemProperty $Key).PSObject.Properties |
             Where-Object { $_.Name -notlike 'PS*' }
    if (-not $props) { Write-Host '  (no overrides set - every app uses the Windows default)'; return }
    foreach ($p in $props) {
        $meaning = switch -Regex ($p.Value) {
            'GpuPreference=1' { 'AMD iGPU (power saving)' }
            'GpuPreference=2' { 'NVIDIA dGPU (high performance)' }
            default           { $p.Value }
        }
        Write-Host ("  {0}`n      -> {1}   [{2}]" -f $p.Name, $p.Value, $meaning)
    }
    Write-Host ''
    Write-Host '=== Adapters present ==='
    Get-CimInstance Win32_VideoController |
        Select-Object Name, DriverVersion, CurrentHorizontalResolution, CurrentVerticalResolution |
        Format-Table -AutoSize | Out-String | Write-Host
}

if ($Show -or -not $App) { Show-Routing; if (-not $App) { return } }

if (-not (Test-Path $Key)) { New-Item -Path $Key -Force | Out-Null }
$exe = $Paths[$App]
Write-Host "App : $App"
Write-Host "Exe : $exe"

$existing = (Get-ItemProperty -Path $Key -Name $exe -ErrorAction SilentlyContinue).$exe

switch ($To) {
    'amd'    { $val = 'GpuPreference=1;' }
    'nvidia' { $val = 'GpuPreference=2;' }
    'auto'   { $val = $null }
}

if ($To -eq 'auto') {
    if ($null -ne $existing) {
        Remove-ItemProperty -Path $Key -Name $exe -ErrorAction SilentlyContinue
        Write-Host "  removed override (was '$existing') - app now follows the Windows default"
    } else {
        Write-Host '  no override was set; nothing to remove'
    }
} else {
    Write-Host "  was : $(if ($null -ne $existing) { $existing } else { '<default>' })"
    Set-ItemProperty -Path $Key -Name $exe -Value $val -Type String
    $label = if ($To -eq 'amd') { 'AMD iGPU' } else { 'NVIDIA dGPU' }
    Write-Host "  now : $val  -> $label"
}

Write-Host ''
Show-Routing
Write-Host 'NOTE: takes effect at the next process launch. Restart the app to apply.'
