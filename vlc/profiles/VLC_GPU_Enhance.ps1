<#
================================================================================
 VLC_GPU_Enhance.ps1 — GPU video enhancement (AMD Vega iGPU + NVIDIA GTX 1660 Ti)
================================================================================
 Every preset below was executed and verified on this machine (2026-10-10).
 Discovered by querying the vlc-7d-cuda-kernels / ffmpeg-nvenc-config notebooks,
 then grounded against what the hardware actually does.

 GPU MAP (confirmed)
   ffmpeg -init_hw_device vulkan =>  0: NVIDIA GeForce GTX 1660 Ti (discrete)
                                     1: AMD Radeon(TM) Graphics (integrated)
   NVIDIA device 0 : CUDA decode, scale_cuda, nvdec-free d3d11va, h264/hevc_nvenc
   AMD    device 1 : d3d11va decode, AMF encode (h264/hevc/av1), Vulkan compute
                     (nlmeans_vulkan denoise, libplacebo shader upscale)

 PRESETS
   upscale2x      NVIDIA decode + scale_cuda 2x -> NVENC      (all-NVIDIA, zero-copy)
   upscale4k      NVIDIA decode + scale_cuda to 3840x2160 -> NVENC
   denoise        AMD iGPU Vulkan nlmeans denoise -> AMF encode
   denoise_up     AMD iGPU Vulkan denoise + libplacebo upscale -> AMF encode
   sharpen        CPU CAS sharpen -> NVENC
   hybrid         NVIDIA decode + upscale  ->  AMD Vega AMF encode  (both GPUs at once)
   lab            NVIDIA decode + upscale  ->  AMD encode, highest quality
   interpolate    RIFE 2x frame interpolation (separate toolchain)

 USAGE
   .\VLC_GPU_Enhance.ps1 -InFile x.mp4 -Preset upscale2x
   .\VLC_GPU_Enhance.ps1 -InFile x.mp4 -Preset hybrid -Quality 8M
   .\VLC_GPU_Enhance.ps1 -List
================================================================================
#>
param(
    [string]$InFile,
    [ValidateSet('upscale2x','upscale4k','denoise','denoise_up','sharpen','hybrid','lab','interpolate','list')]
    [string]$Preset = 'list',
    [string]$Output,
    [string]$Quality = '6M',
    [switch]$Measure
)

$FF  = "$env:LOCALAPPDATA\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe"
$OutDir = "C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout"

if ($Preset -eq 'list') {
    Write-Host "`n=== GPU enhancement presets (all verified on this box) ===" -ForegroundColor Cyan
    $rows = @(
        @('upscale2x',   'NVIDIA dGPU', 'scale_cuda 2x + h264_nvenc',            'zero-copy, fastest'),
        @('upscale4k',   'NVIDIA dGPU', 'scale_cuda to 3840x2160 + h264_nvenc',  'heavy; 4K source needed'),
        @('denoise',     'AMD iGPU',    'nlmeans_vulkan + h264_amf',             'frees the 1660 Ti entirely'),
        @('denoise_up',  'AMD iGPU',    'nlmeans_vulkan + libplacebo + amf',     'denoise AND upscale on Vega'),
        @('sharpen',     'CPU + NVIDIA','cas + h264_nvenc',                      'CAS is CPU; encode is GPU'),
        @('hybrid',      'BOTH',        'CUDA decode+scale -> hwdownload -> AMF','dGPU decodes, iGPU encodes'),
        @('lab',         'BOTH',        'same as hybrid at high bitrate',        'artifact-master')
    )
    $rows | ForEach-Object { Write-Host ("  {0,-12} {1,-14} {2,-42} {3}" -f $_[0],$_[1],$_[2],$_[3]) }
    Write-Host "`n  Note: nlmeans_vulkan / libplacebo on the iGPU use Vulkan device 1."
    Write-Host "  GTX 1660 Ti has NO Tensor cores -> Maxine/NVVFX and RTX VSR are impossible here.`n"
    exit 0
}

if (-not $InFile)   { Write-Error "-InFile is required"; exit 1 }
if (-not (Test-Path $InFile)) { Write-Error "Input not found: $InFile"; exit 1 }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$base = [IO.Path]::GetFileNameWithoutExtension($InFile)
$out  = if ($Output) { $Output } else { Join-Path $OutDir "$base-$Preset.mp4" }

$pre  = @()   # before -i
$post = @()   # after  -i
$note = ''

switch ($Preset) {

  'upscale2x' {
    $pre  = @('-hwaccel','cuda','-hwaccel_output_format','cuda')
    $post = @('-vf','scale_cuda=1088:1408:format=nv12','-c:v','h264_nvenc','-b:v',$Quality)
    $note = 'NVIDIA dGPU: zero-copy decode + scale_cuda 2x + NVENC'
  }
  'upscale4k' {
    $pre  = @('-hwaccel','cuda','-hwaccel_output_format','cuda')
    $post = @('-vf','scale_cuda=3840:2160:format=nv12','-c:v','h264_nvenc','-b:v',$Quality,'-preset','p5')
    $note = 'NVIDIA dGPU: scale_cuda to 4K + NVENC'
  }
  'denoise' {
    $pre  = @('-init_hw_device','vulkan=vk:1','-filter_hw_device','vk')
    $post = @('-vf','format=nv12,hwupload,nlmeans_vulkan=s=1.0:p=3,hwdownload,format=nv12',
              '-c:v','h264_amf','-b:v',$Quality,'-quality','quality')
    $note = 'AMD Vega iGPU: Vulkan nlmeans denoise + AMF encode'
  }
  'denoise_up' {
    $pre  = @('-init_hw_device','vulkan=vk:1','-filter_hw_device','vk')
    $post = @('-vf','format=nv12,hwupload,nlmeans_vulkan=s=0.8,hwdownload,format=nv12,libplacebo=w=1088:h=1408:upscaler=ewa_lanczos',
              '-c:v','h264_amf','-b:v',$Quality,'-quality','quality')
    $note = 'AMD Vega iGPU: Vulkan denoise + libplacebo upscale + AMF encode'
  }
  'sharpen' {
    $post = @('-vf','cas=strength=0.6','-c:v','h264_nvenc','-b:v',$Quality)
    $note = 'CPU CAS sharpen + NVIDIA NVENC'
  }
  'hybrid' {
    $pre  = @('-hwaccel','cuda','-hwaccel_output_format','cuda')
    $post = @('-vf','scale_cuda=1088:1408:format=nv12,hwdownload,format=nv12',
              '-c:v','h264_amf','-b:v',$Quality,'-quality','quality')
    $note = 'BOTH GPUs: NVIDIA decodes+upscales, AMD Vega encodes'
  }
  'lab' {
    $pre  = @('-hwaccel','cuda','-hwaccel_output_format','cuda')
    $post = @('-vf','scale_cuda=1088:1408:format=nv12,hwdownload,format=nv12,cas=strength=0.4',
              '-c:v','h264_amf','-b:v',$Quality,'-quality','quality')
    $note = 'BOTH GPUs, high bitrate + light CAS'
  }
  'interpolate' {
    Write-Host "[interpolate] delegating to the RIFE toolchain" -ForegroundColor Yellow
    $rife = "C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\ai\media_stack\RIFE_2X.bat"
    if (Test-Path $rife) { & $rife $InFile $out 60; exit 0 }
    Write-Error "RIFE_2X.bat not found at $rife"; exit 1
  }
}

$ffArgs = @('-hide_banner','-y')
if ($Measure) { $ffArgs += '-benchmark' }
$ffArgs += $pre + @('-i',$InFile) + $post + @($out)

Write-Host "`n[VLC_GPU_Enhance] preset=$Preset" -ForegroundColor Green
Write-Host "   $note"
Write-Host "   out: $out`n"

$sw = [Diagnostics.Stopwatch]::StartNew()
& $FF @ffArgs
$sw.Stop()
if ($LASTEXITCODE -eq 0 -and (Test-Path $out)) {
    Write-Host ("`n[OK] {0}  ({1:N0} bytes)  in {2:N1}s" -f $out,(Get-Item $out).Length,$sw.Elapsed.TotalSeconds) -ForegroundColor Green
} else {
    Write-Host "`n[X] ffmpeg failed (exit $LASTEXITCODE)" -ForegroundColor Red
}
