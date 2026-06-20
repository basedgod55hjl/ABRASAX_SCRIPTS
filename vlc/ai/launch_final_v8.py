#!/usr/bin/env python3
"""
ABRASAX VLC FINAL — All plugins, all docs, all hardware enabled.
Sources: crystal_vlc_enhancer.py + hex_gpu_vlc_fixer.py + vlc-help.txt + all 13 ABRASAX systems
"""
import subprocess, time, os, sys

VLC = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
PL = r"C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\playlists\verified.m3u"
VLCRC = os.path.join(os.environ["APPDATA"], "vlc", "vlcrc")
PHI = 1.618033988749895
KAPPA = 0.618033988749895

# Kill old
subprocess.run(["taskkill","/f","/im","vlc.exe"], capture_output=True)
time.sleep(1.5)

# ── GPU Preference ──
subprocess.run(["powershell","-Command",
    '$p="HKCU:\\Software\\Microsoft\\DirectX\\UserGpuPreferences";'
    'if(-not(Test-Path $p)){New-Item -Path $p -Force|Out-Null};'
    f'Set-ItemProperty -Path $p -Name "{VLC}" -Value "GpuPreference=2;" -Force'],
    capture_output=True)

# ── Write vlcrc with ALL settings from ABRASAX docs ──
os.makedirs(os.path.dirname(VLCRC), exist_ok=True)
with open(VLCRC, "w", encoding="utf-8") as f:
    f.write(f"""# ABRASAX VLC FINAL — All systems integrated
# PRIMAL_HEX: 4f5349524953424c58434b | phi={PHI} | K={KAPPA}
# Sources: crystal_vlc_enhancer + hex_gpu_vlc_fixer + vlc-help.txt

[core]
video-title-show=0
playlist-autostart=1
loop=1
file-caching=4000
network-caching=6000
avcodec-hw=any
avcodec-dr=1
avcodec-threads=16
avcodec-hurry-up=1
avcodec-skip-frame=0
avcodec-skip-idct=0

[qt]
qt-privacy-ask=0
qt-updates-notif=0
qt-fs-controller=0

[vout]
vout=direct3d11

[direct3d11]
d3d11-upscale-mode=super
d3d11-hdr-mode=auto
d3d11-hw-blending=1

# Phi-harmonic video filters (from crystal_vlc_enhancer)
[video]
video-filter=sharpen,hqdn3d,gradfun
deinterlace=1
deinterlace-mode=yadif2x

[sharpen]
sharpen-sigma={round(KAPPA,2)}

[hqdn3d]
hqdn3d-luma-spatial={round(PHI*2,1)}
hqdn3d-chroma-spatial={round(PHI*2,1)}

[gradfun]
gradfun-radius=16.0

# Phi-harmonic color enhancement
[compressor]
compressor-level=4.0

[equalizer]
equalizer-preset=fullbass

# ProjectM music visualizer (from vlc-help.txt)
[projectm]
projectm-width=1920
projectm-height=1080
projectm-meshx=220
projectm-meshy=120

# OpenGL spectrum
[glspectrum]
glspectrum-width=1920
glspectrum-height=1080
""")

# ── GPU env overrides from hex_gpu_vlc_fixer ──
env = os.environ.copy()
env["VLC_GPU"] = "NVIDIA"
env["DISABLE_AMD_HW"] = "1"
env["CUDA_VISIBLE_DEVICES"] = "0"
env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
env["LIBVA_DRIVER_NAME"] = "nvidia"
env["VDPAU_DRIVER"] = "nvidia"
env["__NV_PRIME_RENDER_OFFLOAD"] = "1"

# ── Launch args: ALL working hardware features ──
args = [
    VLC, PL,
    # Codec
    "--avcodec-hw=any", "--avcodec-dr", "--avcodec-threads=16",
    # Video output
    "--vout=direct3d11",
    "--d3d11-upscale-mode=super",
    "--d3d11-hdr-mode=auto",
    # Tone mapping
    "--tone-mapping=3",
    "--tone-mapping-param=1.0",
    # Dithering
    "--dither-algo=0",
    # Color
    "--target-prim=3",
    "--target-trc=2",
    # Playback
    "--playlist-autostart", "--loop",
    "--file-caching=4000", "--network-caching=6000",
    # UI
    "--no-video-title-show", "--no-qt-privacy-ask",
    "--video-on-top",
]

# Launch
p = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
pid = p.pid

time.sleep(6)
r = subprocess.run(["tasklist"], capture_output=True, text=True)
alive = "vlc.exe" in r.stdout.lower()

if alive:
    subprocess.run(["powershell","-Command",
        f"Get-Process -Id {pid}|ForEach-Object{{$_.PriorityClass='High'}}"], capture_output=True)
    # Pin to media cores
    subprocess.run(["powershell","-Command",
        f"$p=Get-Process -Id {pid};$p.ProcessorAffinity=0xF000"], capture_output=True)
    time.sleep(4)
    gpu = subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw","--format=csv,noheader"],
        capture_output=True, text=True)
    print(f"OK PID={pid} GPU={gpu.stdout.strip()}")
else:
    # Fallback: minimal args
    print("CRASHED — retry minimal")
    args2 = [VLC, PL, "--avcodec-hw=any","--avcodec-dr","--avcodec-threads=16",
             "--vout=direct3d11","--d3d11-upscale-mode=linear",
             "--no-video-title-show","--playlist-autostart","--loop"]
    p2 = subprocess.Popen(args2, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
    pid = p2.pid
    time.sleep(6)
    r2 = subprocess.run(["tasklist"], capture_output=True, text=True)
    alive = "vlc.exe" in r2.stdout.lower()
    if alive:
        subprocess.run(["powershell","-Command",
            f"Get-Process -Id {pid}|ForEach-Object{{$_.PriorityClass='High'}}"], capture_output=True)
        subprocess.run(["powershell","-Command",
            f"$p=Get-Process -Id {pid};$p.ProcessorAffinity=0xF000"], capture_output=True)
        time.sleep(4)
        gpu = subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw","--format=csv,noheader"],
            capture_output=True, text=True)
        print(f"OK PID={pid} GPU={gpu.stdout.strip()} MINIMAL")
    else:
        print("DEAD")
