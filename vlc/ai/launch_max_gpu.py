import subprocess, time

# Kill old VLC
subprocess.run(["taskkill", "/f", "/im", "vlc.exe"], capture_output=True)
time.sleep(2)

vlc = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
pl = r"C:\Users\BASEDGOD\Desktop\VLC_ABRASAX\playlists\verified.m3u"

# MAX GPU config — NVDEC + all threads + hardware blending
args = [
    vlc,
    pl,
    "--avcodec-hw=nvdec",
    "--avcodec-dr",
    "--avcodec-threads=0",      # 0 = auto = ALL 16 threads
    "--avcodec-hurry-up",
    "--vout=direct3d11",
    "--d3d11-upscale-mode=linear",
    "--d3d11-hdr-mode=auto",
    "--d3d11-hw-blending",
    "--no-video-title-show",
]

print("Launching VLC MAX GPU (NVDEC)...")
p = subprocess.Popen(
    args,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
)
pid = p.pid
print(f"PID: {pid}")

# Monitor at intervals
for t in [6, 14, 22, 30]:
    time.sleep(8)
    r = subprocess.run(["tasklist"], capture_output=True, text=True)
    alive = "vlc.exe" in r.stdout.lower()

    gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used,power.draw,temperature.gpu,clocks.current.sm,clocks.current.memory",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
    )

    # CPU load
    cpu = subprocess.run(
        [
            "powershell",
            "-Command",
            "(Get-CimInstance Win32_Processor).LoadPercentage",
        ],
        capture_output=True,
        text=True,
    )

    status = "ALIVE" if alive else "DEAD"
    print(
        f"  {t}s: {status} | GPU: {gpu.stdout.strip()} | CPU: {cpu.stdout.strip()}%"
    )

    if not alive:
        print("  CRASHED!")
        exit(1)

# Set High priority
subprocess.run(
    [
        "powershell",
        "-Command",
        f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | ForEach-Object {{ $_.PriorityClass = 'High' }}",
    ],
    capture_output=True,
)

# Check what video engine is being used
print("\nChecking NVIDIA video decode...")
nvsmi = subprocess.run(
    ["nvidia-smi", "pmon", "-c", "1", "-s", "u"],
    capture_output=True,
    text=True,
)
for line in nvsmi.stdout.strip().split("\n"):
    if "vlc" in line.lower():
        print(f"  {line.strip()}")

print(f"\nVLC running at PID {pid} with NVDEC + 16 threads + D3D11 HW blending")
print("GPU offload: MAX")
