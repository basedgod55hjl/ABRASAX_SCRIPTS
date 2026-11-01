#!/usr/bin/env python3
"""
ABRASAX NVIDIA → AMD iGPU HETEROGENEOUS GPU PIPELINE v1.0
PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618 | K: 0.618

ARCHITECTURE:
  ┌─────────────────────────────────────────────────────────┐
  │  NVIDIA GTX 1660 Ti (6GB VRAM, PCIe 3.0 x16)           │
  │  ┌──────────┐   ┌──────────┐   ┌──────────────────┐    │
  │  │ NVDEC    │ → │ VRAM     │ → │ D3D11VA Surface  │    │
  │  │ Decoder  │   │ Buffer   │   │ (shared/cross)   │    │
  │  └──────────┘   └──────────┘   └───────┬──────────┘    │
  └─────────────────────────────────────────┼───────────────┘
                                            │ PCIe/DMA copy
                                            ▼
  ┌─────────────────────────────────────────────────────────┐
  │  AMD Radeon iGPU (512MB, integrated)                    │
  │  ┌──────────────┐   ┌──────────────┐   ┌──────────┐   │
  │  │ D3D11 Output │ ← │ Framebuffer  │ ← │ Display  │   │
  │  │ Renderer     │   │ (shared VRAM)│   │ (1920x)  │   │
  │  └──────────────┘   └──────────────┘   └──────────┘   │
  └─────────────────────────────────────────────────────────┘

VLC Pipeline:
  1. avcodec-hw=d3d11va on NVIDIA adapter → VRAM decode
  2. D3D11VA surfaces stay in NVIDIA VRAM
  3. VLC vout renders to D3D11 swapchain on NVIDIA
  4. DWM copies presented frame to AMD iGPU framebuffer
  5. AMD iGPU scans out to physical display

STATUS: GTX 1660 Ti → PCIe 3.0 x16 → Radeon iGPU → Display
"""
import subprocess, time, os, sys, json, ctypes, threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# ═══ CONSTANTS ═══
PHI = 1.618033988749895
K = 0.6180339887498949
PRIMAL_HEX = "4f5349524953424c58434b"

NVIDIA_NAME = "NVIDIA GeForce GTX 1660 Ti"
NVIDIA_VRAM_MB = 6144
NVIDIA_PCIE_GEN = 3
NVIDIA_DRIVER = "592.27"

AMD_NAME = "AMD Radeon(TM) Graphics"
AMD_VRAM_MB = 512
AMD_DRIVER = "31.0.21923.11000"

VLC_EXE = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
SCRIPTS_ROOT = Path(r"C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc")
PLAYLISTS = SCRIPTS_ROOT / "playlists"

# ═══════════════════════════════════════════════════════════════
# GPU DETECTION
# ═══════════════════════════════════════════════════════════════

@dataclass
class GPUInfo:
    name: str
    vendor: str  # "nvidia" or "amd"
    vram_mb: int
    driver: str
    pcie_gen: int = 0
    is_display: bool = False
    pnp_id: str = ""
    adapter_index: int = -1

def detect_gpus():
    """Detect all GPUs and their roles."""
    gpus = []

    # NVIDIA via nvidia-smi
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,pcie.link.gen.current",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            parts = [x.strip() for x in r.stdout.strip().split(", ")]
            if len(parts) >= 3:
                gpus.append(GPUInfo(
                    name=parts[0], vendor="nvidia",
                    vram_mb=int(float(parts[1])),
                    driver=parts[2],
                    pcie_gen=int(parts[3]) if len(parts) > 3 else 0
                ))
    except: pass

    # AMD via WMI
    try:
        r = subprocess.run(
            ["wmic", "path", "Win32_VideoController",
             "get", "name,AdapterRAM,DriverVersion,PNPDeviceID",
             "/format:csv"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.split("\n"):
            if "Radeon" in line or ("AMD" in line.upper()):
                parts = line.split(",")
                if len(parts) >= 4:
                    name = parts[3].strip() if len(parts) > 3 else parts[0]
                    ram = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 0
                    gpus.append(GPUInfo(
                        name=name.strip('"'),
                        vendor="amd",
                        vram_mb=ram // (1024*1024) if ram > 1024*1024 else ram,
                        driver=parts[2].strip() if len(parts) > 2 else "unknown",
                        pnp_id=parts[0].strip()
                    ))
    except: pass

    # Determine which GPU drives the display
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_VideoController | "
             "Where-Object {$_.CurrentHorizontalResolution -gt 0} | "
             "Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=5
        )
        display_gpu = r.stdout.strip()
        for g in gpus:
            if g.name[:20] in display_gpu or display_gpu[:20] in g.name:
                g.is_display = True
    except: pass

    return gpus


# ═══════════════════════════════════════════════════════════════
# PCIe BANDWIDTH CALCULATOR
# ═══════════════════════════════════════════════════════════════

def pcie_bandwidth(gen: int, lanes: int = 16) -> float:
    """Calculate PCIe bandwidth in GB/s.
    Gen 1: 250 MB/s/lane, Gen 2: 500, Gen 3: ~985, Gen 4: ~1969
    """
    per_lane = {1: 0.25, 2: 0.5, 3: 0.985, 4: 1.969, 5: 3.938}
    return per_lane.get(gen, 0.25) * lanes

def cross_gpu_bandwidth() -> dict:
    """Estimate NVIDIA→AMD cross-GPU bandwidth."""
    # This goes through PCIe bus since NVIDIA doesn't have display outputs connected
    bw = pcie_bandwidth(NVIDIA_PCIE_GEN, 16)
    return {
        "path": "NVIDIA VRAM → PCIe 3.0 x16 → System RAM → AMD iGPU",
        "theoretical_gbps": round(bw, 1),
        "effective_gbps": round(bw * 0.75, 1),  # ~75% efficiency
        "per_frame_1080p_mb": 1920 * 1080 * 4 / (1024 * 1024),  # ~7.9 MB per RGBA frame
        "max_fps_theoretical": round(bw * 1000 / (1920 * 1080 * 4 / (1024 * 1024))),
        "note": "DWM handles cross-adapter present; ~0.5-2ms latency per frame"
    }


# ═══════════════════════════════════════════════════════════════
# GPU MONITOR (both GPUs simultaneously)
# ═══════════════════════════════════════════════════════════════

class DualGPUMonitor:
    """Monitor both NVIDIA and AMD GPU simultaneously."""

    def __init__(self):
        self.nvml = None
        self._load_nvml()

    def _load_nvml(self):
        for p in [r"C:\Windows\System32\nvml.dll",
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"]:
            if os.path.exists(p):
                try: self.nvml = ctypes.CDLL(p); return
                except: pass

    def snapshot_nvidia(self) -> dict:
        """NVIDIA GPU telemetry."""
        if not self.nvml:
            return self._nvidia_cli()

        try:
            class Mem(ctypes.Structure):
                _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                           ("used", ctypes.c_ulonglong)]
            class Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            f_init = self.nvml.nvmlInit_v2; f_init.restype = ctypes.c_int
            if f_init() != 0: return self._nvidia_cli()

            count = ctypes.c_uint(0)
            self.nvml.nvmlDeviceGetCount_v2(ctypes.byref(count))

            h = ctypes.c_void_p()
            self.nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h))

            mem = Mem(); util = Util()
            temp = ctypes.c_uint(0); pwr = ctypes.c_uint(0)

            self.nvml.nvmlDeviceGetMemoryInfo(h, ctypes.byref(mem))
            self.nvml.nvmlDeviceGetUtilizationRates(h, ctypes.byref(util))
            self.nvml.nvmlDeviceGetTemperature(h, 0, ctypes.byref(temp))
            self.nvml.nvmlDeviceGetPowerUsage(h, ctypes.byref(pwr))

            # PCIe throughput via nvidia-smi
            pcie_rx, pcie_tx = 0, 0
            try:
                r = subprocess.run(
                    ["nvidia-smi", "--query-gpu=pcie.rx.throughput,pcie.tx.throughput",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0:
                    parts = [x.strip() for x in r.stdout.strip().split(", ")]
                    if len(parts) >= 2:
                        pcie_rx = int(parts[0]) if parts[0].isdigit() else 0
                        pcie_tx = int(parts[1]) if parts[1].isdigit() else 0
            except: pass

            self.nvml.nvmlShutdown()

            return {
                "gpu": "NVIDIA",
                "vram_used_mb": round(mem.used / (1024*1024), 1),
                "vram_total_mb": round(mem.total / (1024*1024), 1),
                "vram_pct": round(mem.used / mem.total * 100, 1) if mem.total > 0 else 0,
                "gpu_util_pct": util.gpu,
                "mem_util_pct": util.memory,
                "temp_c": temp.value,
                "power_w": round(pwr.value / 1000.0, 1),
                "pcie_rx_kbps": pcie_rx * 1000,
                "pcie_tx_kbps": pcie_tx * 1000,
            }
        except: return self._nvidia_cli()

    def _nvidia_cli(self) -> dict:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,"
                 "utilization.memory,temperature.gpu,power.draw,pcie.rx.throughput,"
                 "pcie.tx.throughput",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0 or not r.stdout.strip():
                return {"gpu": "NVIDIA", "error": "unavailable"}
            parts = [x.strip() for x in r.stdout.strip().split(", ")]
            return {
                "gpu": "NVIDIA",
                "vram_used_mb": float(parts[0]) if len(parts)>0 else 0,
                "vram_total_mb": float(parts[1]) if len(parts)>1 else 0,
                "gpu_util_pct": float(parts[2]) if len(parts)>2 else 0,
                "mem_util_pct": float(parts[3]) if len(parts)>3 else 0,
                "temp_c": float(parts[4]) if len(parts)>4 else 0,
                "power_w": float(parts[5]) if len(parts)>5 else 0,
                "pcie_rx_kbps": float(parts[6])*1000 if len(parts)>6 and parts[6].isdigit() else 0,
                "pcie_tx_kbps": float(parts[7])*1000 if len(parts)>7 and parts[7].isdigit() else 0,
            }
        except: return {"gpu": "NVIDIA", "error": "unavailable"}

    def snapshot_amd(self) -> dict:
        """AMD iGPU telemetry (limited via WMI)."""
        try:
            # Get AMD process VRAM usage via perf counters
            r = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_VideoController | "
                 "Where-Object {$_.Name -like '*Radeon*' -or $_.Name -like '*AMD*'} | "
                 "Select-Object Name,AdapterRAM,CurrentHorizontalResolution,"
                 "CurrentVerticalResolution,CurrentRefreshRate | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                if isinstance(data, list): data = data[0]
                vram = int(data.get("AdapterRAM", 0)) // (1024*1024)
                return {
                    "gpu": "AMD",
                    "vram_total_mb": vram,
                    "vram_used_mb": vram * 0.4,  # estimated
                    "resolution": f"{data.get('CurrentHorizontalResolution', '?')}x{data.get('CurrentVerticalResolution', '?')}",
                    "refresh_hz": data.get("CurrentRefreshRate", 0),
                    "role": "DISPLAY OUTPUT"
                }
        except: pass
        return {"gpu": "AMD", "role": "DISPLAY OUTPUT", "error": "limited telemetry"}


# ═══════════════════════════════════════════════════════════════
# VLC HYBRID GPU LAUNCHER
# ═══════════════════════════════════════════════════════════════

def set_nvidia_gpu_preference():
    """Force Windows to prefer NVIDIA for VLC."""
    subprocess.run(
        ["powershell", "-Command",
         '$p="HKCU:\\Software\\Microsoft\\DirectX\\UserGpuPreferences";'
         'if(-not(Test-Path $p)){New-Item -Path $p -Force|Out-Null};'
         'Set-ItemProperty -Path $p -Name '
         '"C:\\Program Files\\VideoLAN\\VLC\\vlc.exe" '
         '-Value "GpuPreference=2;" -Force'],
        capture_output=True
    )

def launch_vlc_hybrid(playlist=None):
    """Launch VLC with NVIDIA decode + AMD display pipeline."""
    if playlist is None:
        playlist = PLAYLISTS / "verified.m3u"

    if not Path(playlist).exists():
        print(f"ERROR: Playlist not found: {playlist}")
        return None

    # Kill existing VLC
    subprocess.run(["taskkill", "/f", "/im", "vlc.exe"], capture_output=True)
    time.sleep(1.5)

    # Set NVIDIA preference
    set_nvidia_gpu_preference()

    # Launch with NVIDIA decode + D3D11 output (Windows routes display via AMD)
    args = [
        VLC_EXE, str(playlist),
        # NVIDIA hardware decode
        "--avcodec-hw=d3d11va",      # D3D11VA on NVIDIA adapter
        "--avcodec-dr",
        "--avcodec-threads=16",
        # D3D11 output (will present via AMD iGPU display)
        "--vout=direct3d11",
        "--d3d11-upscale-mode=linear",
        "--d3d11-hdr-mode=auto",
        # Performance
        "--file-caching=3000",
        "--network-caching=5000",
        "--playlist-autostart",
        "--loop",
        "--no-video-title-show",
        "--video-on-top",
        "--no-qt-privacy-ask",
    ]

    p = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )

    time.sleep(5)
    return p


# ═══════════════════════════════════════════════════════════════
# PIPELINE DASHBOARD
# ═══════════════════════════════════════════════════════════════

def print_pipeline_dashboard(monitor: DualGPUMonitor, vlc_pid: int = None):
    """Display the full NVIDIA→AMD pipeline status."""
    nv = monitor.snapshot_nvidia()
    amd = monitor.snapshot_amd()
    bw = cross_gpu_bandwidth()

    print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║         ABRASAX NVIDIA → AMD iGPU HYBRID PIPELINE                      ║
║         PRIMAL_HEX: {PRIMAL_HEX}                        ║
╚══════════════════════════════════════════════════════════════════════════╝

  ╔═══ PIPELINE ARCHITECTURE ═══════════════════════════════════════════╗
  ║                                                                      ║
  ║  [NVIDIA GTX 1660 Ti]                [AMD Radeon iGPU]              ║
  ║  ┌─────────────────┐                 ┌─────────────────┐            ║
  ║  │ Video Decode    │    PCIe 3.0     │ Display Output  │            ║
  ║  │ (D3D11VA/NVDEC) │ ═══════════════→│ (D3D11 Present) │            ║
  ║  │ VRAM: {nv.get('vram_used_mb',0):.0f}/{nv.get('vram_total_mb',0):.0f} MB     │                 │ 1920x1080       │            ║
  ║  │ GPU: {nv.get('gpu_util_pct',0):.0f}% | {nv.get('temp_c',0):.0f}°C           │                 │                 │            ║
  ║  └────────┬────────┘                 └────────┬────────┘            ║
  ║           │ PCIe TX: {nv.get('pcie_tx_kbps',0):.0f} KB/s         │ DWM Copy       │            ║
  ║           └──────────────────────────────────┘                    ║
  ║                                                                      ║
  ╚══════════════════════════════════════════════════════════════════════╝

  ╔═══ GPU DETAILS ════════════════════════════════════════════════════╗
  ║ NVIDIA: {NVIDIA_NAME}                                        ║
  ║   VRAM: {nv.get('vram_used_mb',0):.0f}/{nv.get('vram_total_mb',0):.0f} MB ({nv.get('vram_pct',0):.0f}%)                                            ║
  ║   GPU: {nv.get('gpu_util_pct',0):.0f}% | MEM: {nv.get('mem_util_pct',0):.0f}% | TEMP: {nv.get('temp_c',0):.0f}°C | POWER: {nv.get('power_w',0):.0f}W          ║
  ║   PCIe: RX {nv.get('pcie_rx_kbps',0):.0f} KB/s | TX {nv.get('pcie_tx_kbps',0):.0f} KB/s (Gen {NVIDIA_PCIE_GEN} x16)                      ║
  ║   Driver: {NVIDIA_DRIVER}                                                      ║
  ║                                                                      ║
  ║ AMD: {AMD_NAME}                                    ║
  ║   VRAM: {AMD_VRAM_MB} MB (shared with system RAM)                              ║
  ║   Display: {amd.get('resolution', '?')} @ {amd.get('refresh_hz', '?')}Hz                                           ║
  ║   Role: DISPLAY OUTPUT (DWM cross-adapter present)                  ║
  ║   Driver: {AMD_DRIVER}                                                 ║
  ╚══════════════════════════════════════════════════════════════════════╝

  ╔═══ CROSS-GPU BANDWIDTH ════════════════════════════════════════════╗
  ║ Path: {bw['path']}   ║
  ║ Theoretical: {bw['theoretical_gbps']} GB/s | Effective: ~{bw['effective_gbps']} GB/s                               ║
  ║ Per 1080p frame: {bw['per_frame_1080p_mb']:.1f} MB RGBA                                        ║
  ║ Max theoretical FPS: ~{bw['max_fps_theoretical']:,} fps                                        ║
  ╚══════════════════════════════════════════════════════════════════════╝

  ╔═══ VLC STATUS ═════════════════════════════════════════════════════╗
  ║ PID: {vlc_pid or 'N/A'}                                                     ║
  ║ Decode: D3D11VA on NVIDIA adapter (GpuPreference=2)               ║
  ║ Output: Direct3D11 → DWM → AMD iGPU display                        ║
  ║ Latency: ~0.5-2ms per frame (cross-adapter copy)                   ║
  ╚══════════════════════════════════════════════════════════════════════╝
""")


# ═══════════════════════════════════════════════════════════════
# LIVE MONITORING LOOP
# ═══════════════════════════════════════════════════════════════

def live_monitor(interval: float = 5.0):
    """Continuously monitor both GPUs and the pipeline."""
    monitor = DualGPUMonitor()
    vlc_pid = None

    # Find VLC PID
    try:
        r = subprocess.run(["tasklist", "/fi", "IMAGENAME eq vlc.exe", "/fo", "csv"],
                          capture_output=True, text=True, timeout=3)
        for line in r.stdout.split("\n"):
            if "vlc.exe" in line.lower():
                vlc_pid = line.split('","')[1] if '","' in line else None
                break
    except: pass

    print("\n" + "="*70)
    print("  ABRASAX NVIDIA→AMD LIVE PIPELINE MONITOR")
    print(f"  Press Ctrl+C to stop  |  Refresh: {interval}s")
    print("="*70)

    iteration = 0
    try:
        while True:
            iteration += 1
            # Re-detect VLC PID each iteration
            try:
                r = subprocess.run(["tasklist", "/fi", "IMAGENAME eq vlc.exe", "/fo", "csv"],
                                  capture_output=True, text=True, timeout=3)
                vlc_pid = None
                for line in r.stdout.split("\n"):
                    if "vlc.exe" in line.lower():
                        parts = line.split('","')
                        if len(parts) > 1:
                            vlc_pid = parts[1].strip('"')
                        break
            except: pass

            nv = monitor.snapshot_nvidia()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iter {iteration} | VLC: {'RUNNING' if vlc_pid else 'DEAD'} | "
                  f"NVIDIA: {nv.get('gpu_util_pct',0):.0f}% GPU | {nv.get('vram_used_mb',0):.0f}MB VRAM | "
                  f"PCIe TX: {nv.get('pcie_tx_kbps',0):.0f} KB/s | {nv.get('temp_c',0):.0f}°C")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ABRASAX NVIDIA→AMD Hybrid GPU Pipeline")
    parser.add_argument("--playlist", "-p", help="Playlist to launch")
    parser.add_argument("--mode", "-m", default="dashboard",
                       choices=["dashboard", "launch", "monitor", "info"],
                       help="Operation mode")
    parser.add_argument("--interval", "-i", type=float, default=5.0,
                       help="Monitor refresh interval (seconds)")

    args = parser.parse_args()

    if args.mode == "info":
        gpus = detect_gpus()
        bw = cross_gpu_bandwidth()
        print("\nDETECTED GPUS:")
        for g in gpus:
            print(f"  {g.vendor.upper()}: {g.name}")
            print(f"    VRAM: {g.vram_mb}MB | Display: {g.is_display}")
        print(f"\nCROSS-GPU BANDWIDTH:")
        print(f"  {bw['path']}")
        print(f"  {bw['theoretical_gbps']} GB/s theoretical")
        return

    elif args.mode == "dashboard":
        monitor = DualGPUMonitor()
        vlc_pid = None
        try:
            r = subprocess.run(["tasklist", "/fi", "IMAGENAME eq vlc.exe", "/fo", "csv"],
                              capture_output=True, text=True, timeout=3)
            for line in r.stdout.split("\n"):
                if "vlc.exe" in line.lower():
                    parts = line.split('","')
                    if len(parts) > 1:
                        vlc_pid = parts[1].strip('"')
                    break
        except: pass
        print_pipeline_dashboard(monitor, vlc_pid)

    elif args.mode == "launch":
        playlist = args.playlist or str(PLAYLISTS / "verified.m3u")
        p = launch_vlc_hybrid(playlist)
        if p:
            time.sleep(3)
            monitor = DualGPUMonitor()
            print_pipeline_dashboard(monitor, p.pid)
        else:
            print("VLC launch failed.")

    elif args.mode == "monitor":
        live_monitor(args.interval)


if __name__ == "__main__":
    main()
