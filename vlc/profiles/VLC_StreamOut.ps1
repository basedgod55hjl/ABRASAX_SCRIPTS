<#
================================================================================
 VLC_StreamOut.ps1 — wire up VLC's built-in stream_out plugins
 (20 plugins ship with VLC 3.0.24 and were completely unused).

 USAGE
   Record    : .\VLC_StreamOut.ps1 -Mode record    -Input <file> [-Output out.ts]
   Transcode : .\VLC_StreamOut.ps1 -Mode transcode -Input <file> [-Output out.mp4]
   Cast      : .\VLC_StreamOut.ps1 -Mode cast      -Input <file> [-CastIp 192.168.1.50]
   List      : .\VLC_StreamOut.ps1 -Mode list

 All modes are headless-capable (-Headless) so they can run as background jobs.
================================================================================
#>
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('record','transcode','cast','list')]
    [string]$Mode,

    [string]$Input,
    [string]$Output,
    [string]$CastIp,
    [switch]$Headless,
    [int]$RunSeconds = 0        # >0 = stop after N seconds (useful for testing)
)

$VLC = "C:\Program Files\VideoLAN\VLC\vlc.exe"

function Show-StreamOutPlugins {
    Write-Host "`n=== stream_out plugins shipped with VLC 3.0.24 ===" -ForegroundColor Cyan
    $dir = "C:\Program Files\VideoLAN\VLC\plugins\stream_out"
    Get-ChildItem $dir -Filter "libstream_out_*_plugin.dll" |
        ForEach-Object { $_.Name -replace '^libstream_out_','' -replace '_plugin\.dll$','' } |
        Sort-Object | ForEach-Object { Write-Host "   $_" }
    Write-Host ""
}

if ($Mode -eq 'list') { Show-StreamOutPlugins; exit 0 }

if (-not $Input)      { Write-Error "-Input is required for -Mode $Mode"; exit 1 }
if (-not (Test-Path $Input)) { Write-Error "Input not found: $Input"; exit 1 }

$base   = [System.IO.Path]::GetFileNameWithoutExtension($Input)
$outDir = "C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

switch ($Mode) {

    'record' {
        # stream_out/record: remux the input to disk with no re-encode.
        if (-not $Output) { $Output = Join-Path $outDir "$base-record.ts" }
        $sout = "#record{dst=`"$Output`"}"
        Write-Host "[record] $Input -> $Output (no re-encode, remux)" -ForegroundColor Green
    }

    'transcode' {
        # stream_out/transcode: re-encode to H.264 + AAC in MP4.
        if (-not $Output) { $Output = Join-Path $outDir "$base-transcoded.mp4" }
        $sout = "#transcode{vcodec=h264,vb=4000,acodec=mp4a,ab=128,channels=2,samplerate=44100}:std{access=file,mux=mp4,dst=`"$Output`"}"
        Write-Host "[transcode] $Input -> $Output (H.264 + AAC in MP4)" -ForegroundColor Green
    }

    'cast' {
        # stream_out/chromecast: push to a Chromecast on the LAN.
        if (-not $CastIp) { Write-Error "-CastIp is required for -Mode cast (e.g. 192.168.1.50)"; exit 1 }
        $sout = "#chromecast{ip=$CastIp}"
        Write-Host "[cast] $Input -> Chromecast at $CastIp" -ForegroundColor Green
    }
}

$argList = @()
if ($Headless) { $argList += @('--intf','dummy') }
$argList += @($Input, "--sout=$sout")
if ($Mode -eq 'record' -or $Mode -eq 'transcode') { $argList += '--sout-keep' }

Write-Host ("   vlc " + ($argList -join ' '))

$p = Start-Process -FilePath $VLC -ArgumentList $argList -PassThru

if ($RunSeconds -gt 0) {
    Start-Sleep -Seconds $RunSeconds
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    if (Test-Path $Output) {
        $sz = (Get-Item $Output).Length
        Write-Host ("`n[OK] output written: {0}  ({1:N0} bytes)" -f $Output, $sz) -ForegroundColor Green
    } else {
        Write-Host "`n[X] no output file produced" -ForegroundColor Red
    }
}
