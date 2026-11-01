$ultimate_vlcrc = @"
### ═══════════════════════════════════════════════════════════════
### ABRASAX VLC ULTIMATE MEGACONFIG v12.0 — OSIRISBLXCK
### PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618033988749895 | K: 0.618
###
### MERGED FROM:
###   - launch_ultimate.py (13-phase GPU pipeline + 7D Poincare + Phi Quantum Seed)
###   - launch_abrasax_enhanced.py (AMD offload + NVDEC/NVENC + XOR Brain + VRAM Router)
###   - vlc_ai_engine.py (AI scene detection + smart filter presets + playlist analysis)
###   - nvidia_amd_pipeline.py (NVIDIA→AMD hybrid GPU cross-adapter pipeline)
###   - crystal_7d_engine.py (7D hyperbolic compression + DNA pixel growth + playlist heal)
###   - swarm_orchestrator.py (4-agent swarm for APK build)
###   - LAUNCH_ALL_VLC_ENHANCED.bat (stable + HW + XOR modes)
###   - ABRASAX_VLC_AI_ENHANCE.bat (AI enhancement loop)
###   - 7d_resume.lua + 7d_subtitle.lua (Lua extensions)
###   - vlcrc_GOLDEN.txt (base config)
###   - VLC_STATE.json (crash-proof flags + GpuPreference)
### GPU: GTX 1660 Ti (Turing, 6GB) + AMD Radeon iGPU
### CPU: AMD Ryzen 7 4800H (8C/16T)
### DISPLAY: HP E233 + DELL P2319H (Dual 1920x1080)
###═══════════════════════════════════════════════════════════════

# ================================================================
# CORE
# ================================================================
[core]
video-title-show=0
playlist-autostart=1
loop=1
repeat=0
file-caching=3000
network-caching=5000
live-caching=1000
clock-synchro=0
audio-desync=0
spdif=0
audio-resampler=soxr
audio-resampling-quality=3
one-instance=1
one-instance-when-started-from-file=1
playlist-enqueue=0
media-library=0
extraintf=http:telnet
http-host=127.0.0.1
http-port=8080

# ================================================================
# AVCODEC — GPU DECODE MAX
# ================================================================
[avcodec]
avcodec-hw=any
avcodec-dr=1
avcodec-threads=16
avcodec-hurry-up=1
avcodec-skip-frame=0
avcodec-skip-idct=0
avcodec-error-resilience=1
avcodec-workaround-bugs=1
avcodec-corrupted=1
avcodec-fast=1

# ================================================================
# VIDEO OUTPUT — Direct3D11 + OpenGL DUAL
# ================================================================
[vout]
vout=direct3d11

[direct3d11]
direct3d11-hw-blending=1
d3d11-upscale-mode=linear
d3d11-hdr-mode=auto

[d3d11_filters]
contrast=1.05
brightness=1.02
saturation=1.10
gamma=1.05
hue=0.0

[gl]
rendering-intent=1
tone-mapping=3
dither-algo=1
tone-mapping-desat=0.5

[wgl]
gpu-affinity=0

# ================================================================
# VIDEO FILTER CHAIN — CPU filters OFF (crash/lag under D3D11 hw decode)
# ================================================================
[video]
video-filter=
deinterlace=0

[adjust]
contrast=1.08
brightness=1.02
saturation=1.10
gamma=1.05
hue=0.0
brightness-threshold=0

[sharpen]
sharpen-sigma=0.08

[hqdn3d]
hqdn3d-luma-spat=4.0
hqdn3d-chroma-spat=3.0
hqdn3d-luma-temp=6.0
hqdn3d-chroma-temp=4.5

[postproc]
postproc-q=6
postproc-name=default

[gradfun]
gradfun-radius=16
gradfun-strength=1.2

[gradient]
gradient-mode=gradient
gradient-type=0
gradient-cartoon=1

[grain]
grain-variance=1.5

[motionblur]
blur-factor=60

[posterize]
posterize-level=6

[antiflicker]
antiflicker-window-size=10
antiflicker-softening-size=10

[deinterlace]
sout-deinterlace-mode=blend

[swscale]
swscale-mode=2

# ================================================================
# AUDIO FILTER CHAIN — FULL
# ================================================================
[audio]
audio-filter=compressor,equalizer,spatializer,stereo_widen,normvol,gain

[compressor]
compressor-rms-peak=0.0
compressor-attack=25.0
compressor-release=100.0
compressor-threshold=-20.0
compressor-ratio=8.0
compressor-knee=2.5
compressor-makeup-gain=6.0

[equalizer]
equalizer-preset=fullbass
equalizer-preamp=12.0

[spatializer]
spatializer-roomsize=0.85
spatializer-width=1.0
spatializer-wet=0.4
spatializer-dry=0.6
spatializer-damp=0.2

[stereo_widen]
stereo-widen=180

[normvol]
norm-buff-size=20

[gain]
gain=1.0

[audio-resampler]
soxr-resampler-quality=3

# ================================================================
# VISUALIZERS — ALL ENABLED
# ================================================================
[visual]
effect-list=spectrum
effect-width=800
effect-height=500
effect-fft-window=flat
effect-kaiser-param=3.0
visual-80-bands=1
visual-peaks=1
spect-show-original=0
spect-show-base=1
spect-radius=42
spect-sections=3
spect-color=80
spect-show-bands=1
spect-80-bands=1
spect-separ=1
spect-amp=8
spect-show-peaks=1
spect-peak-width=61
spect-peak-height=1

[goom]
goom-width=800
goom-height=500
goom-speed=6

[projectm]
projectm-width=800
projectm-height=500
projectm-meshx=32
projectm-meshy=24
projectm-texture-size=1024

[glspectrum]
glspectrum-width=800
glspectrum-height=600

# ================================================================
# QT INTERFACE — FULL POWER
# ================================================================
[qt]
qt-minimal-view=0
qt-system-tray=1
qt-notification=1
qt-start-minimized=0
qt-pause-minimized=0
qt-opacity=1.0
qt-fs-opacity=0.85
qt-video-autoresize=1
qt-name-in-title=1
qt-fs-controller=1
qt-recentplay=1
qt-continue=1
qt-dark-palette=1
qt-updates-notif=1
qt-embedded-open=0
qt-advanced-pref=1
qt-error-dialogs=1
qt-privacy-ask=0
qt-fullscreen-screennumber=0
qt-autoload-extensions=1
qt-bgcone=1
qt-bgcone-expands=1
qt-icon-change=1
qt-max-volume=150
qt-fs-sensitivity=3
qt-auto-raise=1
qt-disable-volume-keys=0
qt-slider-colours=153;210;153;20;210;20;255;199;15;245;39;29

# ================================================================
# FREETYPE FONTS
# ================================================================
[freetype]
freetype-font=Arial
freetype-monofont=Courier New
freetype-fontsize=18
freetype-rel-fontsize=0
freetype-opacity=255
freetype-color=16777215
freetype-bold=1
freetype-background-opacity=0
freetype-outline-opacity=200
freetype-outline-color=0
freetype-outline-thickness=3
freetype-shadow-opacity=128
freetype-shadow-color=0

# ================================================================
# SUBTITLES
# ================================================================
[subsdec]
subsdec-align=-1
subsdec-autodetect-utf8=1

[subsdelay]
subsdelay-mode=1
subsdelay-factor=2.0

[ttml]
ttml-align=0

# ================================================================
# LUA EXTENSIONS
# ================================================================
[lua]
lua-intf=dummy
http-password=1SGEjqVD-TGkEu19
telnet-host=localhost
telnet-port=4212
telnet-password=bkN3Bvy-XD_QRT9m

# ================================================================
# SKINS2
# ================================================================
[skins2]
skins2-systray=1
skins2-taskbar=1
skins2-transparency=1
skinned-playlist=1
skinned-video=1

# ================================================================
# STREAM OUTPUT
# ================================================================
[stream_out_transcode]
sout-transcode-deinterlace=1
sout-transcode-deinterlace-module=deinterlace

[prefetch]
prefetch-buffer-size=65536
prefetch-read-size=33554432
prefetch-seek-threshold=16777216

# ================================================================
# NETWORK / SAP
# ================================================================
[sap]
sap-timeout=1800
sap-parse=1

# ================================================================
# FILE LOGGING
# ================================================================
[file]
file-logging=1
logmode=text
log-verbose=2

[logger]

# ================================================================
# DEMUXERS
# ================================================================
[mkv]
mkv-use-ordered-chapters=1
mkv-preload-local-dir=1

[ts]
ts-es-id-pid=1
ts-split-es=1

[ps]
ps-trust-timestamps=1

[playlist]
playlist-skip-ads=1

# ================================================================
# OLD RC (Telnet)
# ================================================================
[oldrc]
rc-host=
rc-quiet=0

# ================================================================
# GESTURES
# ================================================================
[gestures]
gestures-threshold=30
gestures-button=left

# ================================================================
# ADAPTIVE STREAMING
# ================================================================
[adaptive]
adaptive-maxbuffer=30000
adaptive-livedelay=15000
adaptive-lowlatency=-1

# ================================================================
# SCENE (THUMBNAILS)
# ================================================================
[scene]
scene-format=png
scene-ratio=60
scene-prefix=snap_

# ================================================================
# X264 ENCODER (for streaming/recording)
# ================================================================
[x264]
sout-x264-preset=fast
sout-x264-profile=high
sout-x264-tune=film

"@

# FIX: was hard-coded to C:\Users\BASEDGOD (does not exist on this machine)
$vlcrc_path = Join-Path $env:APPDATA 'vlc\vlcrc'
# Backup existing
if (Test-Path $vlcrc_path) {
    $stamp = Get-Date -f 'yyyyMMdd-HHmmss'
    Copy-Item $vlcrc_path "$vlcrc_path.bak-osiris-$stamp" -Force
}
$dir = Split-Path $vlcrc_path -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
Set-Content -Path $vlcrc_path -Value $ultimate_vlcrc -Encoding UTF8 -Force
Write-Output "ULTIMATE_VLCRC_WRITTEN -> $vlcrc_path"
Write-Output "Size: $((Get-Item $vlcrc_path).Length) bytes"
