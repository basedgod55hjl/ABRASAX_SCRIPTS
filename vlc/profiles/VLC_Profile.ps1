<#
================================================================================
 VLC_Profile.ps1 — switchable VLC launch profiles for this hybrid AMD+NVIDIA box
 Builds on the verified golden config: vout=direct3d11 + avcodec-hw=d3d11va +
 file-caching=3000 + GpuPreference=2 (NVIDIA).

 Only ONE profile can be active at a time — they set mutually exclusive
 vout/decoder pairs. This script does NOT edit vlcrc; it passes flags on the
 command line so your saved config always stays the tested one.

 USAGE
   .\VLC_Profile.ps1 -Profile nvidia  [media]   # default / golden (GTX 1660 Ti)
   .\VLC_Profile.ps1 -Profile amd     [media]   # Radeon Vega iGPU renders (frees dGPU)
   .\VLC_Profile.ps1 -Profile dxva2   [media]   # legacy D3D9 fallback decoder
   .\VLC_Profile.ps1 -Profile gl      [media]   # OpenGL output + D3D11<->GL interop
   .\VLC_Profile.ps1 -Profile info              # show what is available/active
================================================================================
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('nvidia','amd','dxva2','gl','info')]
    [string]$Profile,

    [string]$Media = "C:\Users\sirch\Desktop\vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv.xspf",

    [switch]$NoUI      # launch with --intf dummy (for probing/benchmarking)
)

$VLC     = "C:\Program Files\VideoLAN\VLC\vlc.exe"
$VlcReg  = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"
$Script:Report = [ordered]@{}

function Get-VlcGpuPref {
    try { (Get-ItemProperty -Path $VlcReg -Name $VLC -ErrorAction Stop).$VLC } catch { "(unset)" }
}

switch ($Profile) {

    'nvidia' {
        # Golden config: decode AND present on the GTX 1660 Ti.
        $flags = @('--avcodec-hw=d3d11va','--vout=direct3d11','--file-caching=3000',
                   '--avcodec-threads=0','--skip-frames=0','--no-video-title-show')
        $Script:Report['profile']  = 'nvidia (GTX 1660 Ti, d3d11va + direct3d11)'
        $Script:Report['gpupref'] = Get-VlcGpuPref
    }

    'amd' {
        # Radeon Vega iGPU renders; intended to free the 1660 Ti's 6 GB + CUDA.
        # Requires GpuPreference=1 for vlc.exe, which this profile SETS.
        New-Item -Path $VlcReg -Force | Out-Null
        Set-ItemProperty -Path $VlcReg -Name $VLC -Value 'GpuPreference=1;' -Type String
        $flags = @('--avcodec-hw=d3d11va','--vout=direct3d11','--file-caching=3000',
                   '--avcodec-threads=0','--no-video-title-show')
        $Script:Report['profile']  = 'amd (Radeon Vega iGPU, d3d11va + direct3d11)'
        $Script:Report['gpupref']  = 'GpuPreference=1;  (set for ' + $VLC + ')'
        $Script:Report['note']     = 'Takes effect at next vlc.exe start, not for a running one.'
    }

    'dxva2' {
        # Legacy D3D9 decode path. Only for when d3d11va crashes or driver-stalls.
        $flags = @('--avcodec-hw=dxva2','--vout=direct3d11','--file-caching=3000',
                   '--no-video-title-show')
        $Script:Report['profile'] = 'dxva2 (legacy DirectX 9 decoder fallback)'
    }

    'gl' {
        # OpenGL output with D3D11 interop -> unlocks GLSL shader filters.
        $flags = @('--avcodec-hw=d3d11va','--vout=gl','--glconv=glinterop_dxva2',
                   '--file-caching=3000','--no-video-title-show')
        $Script:Report['profile'] = 'gl (OpenGL output + glinterop_dxva2)'
        $Script:Report['note']    = 'Use to chain GLSL video filters; d3d11 remains the safer default.'
    }

    'info' {
        Write-Host "`n=== VLC GPU / capability report ===" -ForegroundColor Cyan
        Write-Host ("vlc.exe GpuPreference : " + (Get-VlcGpuPref))
        Write-Host ("  (2 = high-perf NVIDIA, 1 = power-saving AMD iGPU)")
        Write-Host "`nAdapters:"
        Get-CimInstance Win32_VideoController |
            Select-Object Name, DriverVersion |
            ForEach-Object { Write-Host ("  {0}  [{1}]" -f $_.Name, $_.DriverVersion) }
        Write-Host "`nValid VLC hardware decoders / outputs (from vlc -H):"
        Write-Host "  --avcodec-hw={any,d3d11va,dxva2,none}"
        Write-Host "  --vout=direct3d11 | gl | direct3d9 | ..."
        Write-Host "  --glconv={any,glinterop_dxva2,none}"
        Write-Host "`nProfiles: nvidia (default) | amd | dxva2 | gl`n"
        exit 0
    }
}

$argList = @()
if ($NoUI) { $argList += @('--intf','dummy') }
if ($Media) { $argList += $Media }
$argList += $flags

Write-Host "`n[VLC_Profile] $($Script:Report['profile'])" -ForegroundColor Green
foreach ($k in $Script:Report.Keys) {
    if ($k -ne 'profile') { Write-Host ("   {0,-9}: {1}" -f $k, $Script:Report[$k]) }
}
Write-Host ("   flags    : " + ($flags -join ' '))
Write-Host ""

Start-Process -FilePath $VLC -ArgumentList $argList
