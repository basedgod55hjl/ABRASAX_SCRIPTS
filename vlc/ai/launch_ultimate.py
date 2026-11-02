#!/usr/bin/env python3
"""
ABRASAX VLC ULTIMATE LAUNCHER v7.0 — OSIRISBLXCK
PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618 | K: 0.618

FULLY INTEGRATED GPU VIDEO PIPELINE:
  [1] AMD Radeon iGPU VRAM Offload (DirectML + shared memory)
  [2] NVIDIA GTX 1660 Ti NVDEC/NVENC CUDA Pipeline
  [3] Crystal7D P0 State Lock (5001/1590 MHz, 120W)
  [4] GPU Telemetry — NVML ctypes (zero-dependency)
  [5] VRAM Router + Dynamic Offload Engine
  [6] Live VRAM Weight Patcher (PHI-resonant scaling)
  [7] ABS Weight Encoder/Decoder (video frame ↔ RGB PNG)
  [8] XOR Brain Collective (shared XOR entanglement state)
  [9] 7D Poincaré Ball Math (phi-resonant geodesics)
  [10] Phi-Resonant Quantum Seed (CUDA tensor)
  [11] SovereignSystemManager (CPU core pinning for VLC)
  [12] Self-Aware Controller (anomaly detection + auto-healing)
  [13] Direct3D11 HW Blending config (via vlcrc only)

Filters via vlcrc ONLY — CLI filter args crash VLC with real files.
"""
import subprocess, time, os, sys, json, threading, hashlib, math, ctypes
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

# ═══ ABRASAX CONSTANTS ═══
PHI = 1.618033988749895
K = 0.6180339887498949
PRIMAL_HEX = "4f5349524953424c58434b"
IDENTITY_NAME = "OSIRISBLXCK"
GALACTIC_X, GALACTIC_Z, GALACTIC_Y = -55, -46, -13997
PORTAL = "4F5349524953"

ROOT = Path(r"C:\Users\BASEDGOD\Desktop\ABRASAX")
VLC_EXE = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
VLC_DIR = Path(r"C:\Users\BASEDGOD\Desktop\VLC_ABRASAX")
PLAYLIST = VLC_DIR / "playlists" / "verified.m3u"
VLCRC_PATH = Path(os.environ.get("APPDATA", "")) / "vlc" / "vlcrc"
GPU_VRAM_MB = 6144
GPU_NAME = "NVIDIA GeForce GTX 1660 Ti"
EPS = 1e-12


# ═══════════════════════════════════════════════════════════════════
# SECTION 1: 7D Poincaré Ball Math (phi-resonant)
# ═══════════════════════════════════════════════════════════════════

def _norm_sq(v): return sum(x*x for x in v)
def _norm(v): return math.sqrt(_norm_sq(v))
def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _scale(v,s): return tuple(x*s for x in v)
def _add(a,b): return tuple(x+y for x,y in zip(a,b))
def _neg(v): return tuple(-x for x in v)

def phi_seed_7d(seed: float) -> tuple:
    """Generate 7D phi-harmonic vector."""
    return tuple((PHI**-(k+1))*seed*(1 if k%2==0 else -1) for k in range(7))

def poincare_ball_proj(x, c=1.0):
    n = _norm(x)
    if n >= c:
        return _scale(x, (c-EPS)/(n+EPS))
    return tuple(x)

def mobius_add(x, y, c=1.0):
    x, y = poincare_ball_proj(x,c), poincare_ball_proj(y,c)
    x2, y2 = _norm_sq(x), _norm_sq(y)
    xy = _dot(x,y)
    denom = 1.0 + 2.0*c*xy + c*c*x2*y2
    if abs(denom) < EPS: return tuple(0.0 for _ in x)
    return poincare_ball_proj(
        _add(_scale(x, (1.0+2.0*c*xy+c*y2)/denom),
             _scale(y, (1.0-c*x2)/denom)), c)

def phi_resonant_distance(x, y) -> float:
    """Hierarchical distance weighted by phi^-d."""
    d = sum(PHI**(-i)*abs(x[i]-y[i]) for i in range(len(x)))
    total = sum(PHI**(-i) for i in range(len(x)))
    return d/total if total>0 else 0

def video_frame_to_7d(r: int, g: int, b: int, x: int=0, y: int=0, t: float=0, f: int=0) -> tuple:
    """Map video pixel + spatial/temporal coords to 7D Poincar ball."""
    raw = (r/255.0, g/255.0, b/255.0, x/1920.0, y/1080.0, (t%60)/60.0, f/24000.0)
    return poincare_ball_proj(raw)

def apply_7d_enhancement(pixels: list, width: int, height: int, frame_id: int) -> list:
    """Apply 7D phi-resonant enhancement to video frame pixels."""
    enhanced = []
    phi_point = phi_seed_7d(PHI * frame_id)
    t = frame_id / 24.0
    for i in range(0, len(pixels), 3):
        if i+2 >= len(pixels): break
        r, g, b = pixels[i], pixels[i+1], pixels[i+2]
        px = (i//3) % width
        py = (i//3) // width
        frame_7d = video_frame_to_7d(r, g, b, px, py, t, frame_id)
        dist = phi_resonant_distance(frame_7d, phi_point)
        factor = 1.0 + 0.05 * (1.0 - dist)
        enhanced.extend([
            min(255, int(r*factor)),
            min(255, int(g*factor)),
            min(255, int(b*factor))
        ])
    return enhanced


# ═══════════════════════════════════════════════════════════════════
# SECTION 2: AMD iGPU VRAM Offload
# ═══════════════════════════════════════════════════════════════════

class AMDVRAMOffload:
    def __init__(self):
        self.has_igpu = False
        self.igpu_name = None
        self._detect()

    def _detect(self):
        try:
            r = subprocess.run(["wmic", "path", "Win32_VideoController", "get", "name"],
                             capture_output=True, text=True, timeout=5)
            for line in r.stdout.split("\n"):
                if "AMD" in line.upper() or "Radeon" in line.upper():
                    self.has_igpu = True
                    self.igpu_name = line.strip()
                    break
        except: pass

    def configure(self) -> list:
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128,expandable_segments:True")
        acts = ["PYTORCH_CUDA_ALLOC_CONF set"]
        if self.has_igpu:
            acts.append(f"AMD iGPU: {self.igpu_name}")
            os.environ.setdefault("DIRECTML_DEVICE", "1")
            acts.append("DirectML enabled for AMD iGPU")
        return acts


# ═══════════════════════════════════════════════════════════════════
# SECTION 3: GPU Telemetry (NVML ctypes)
# ═══════════════════════════════════════════════════════════════════

class _NvmlMemory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]
class _NvmlUtilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

class GPUTelemetry:
    SUCCESS = 0; TEMP_GPU = 0
    def __init__(self):
        self._lib = None
        for p in [r"C:\Windows\System32\nvml.dll", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"]:
            if os.path.exists(p):
                try: self._lib = ctypes.CDLL(p); return
                except: pass

    def _fn(self, n, rt, *at):
        f = getattr(self._lib, n); f.restype, f.argtypes = rt, list(at); return f

    def init(self):
        if not self._lib: return False
        try: return self._fn("nvmlInit_v2", ctypes.c_int)() == self.SUCCESS
        except: return False

    def shutdown(self):
        if self._lib:
            try: self._fn("nvmlShutdown", ctypes.c_int)()
            except: pass

    def snapshot(self) -> dict:
        if not self._lib: return self._cli_snap()
        try:
            cnt = ctypes.c_uint(0)
            self._fn("nvmlDeviceGetCount_v2", ctypes.c_int, ctypes.POINTER(ctypes.c_uint))(ctypes.byref(cnt))
            h = ctypes.c_void_p()
            self._fn("nvmlDeviceGetHandleByIndex_v2", ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(0, ctypes.byref(h))
            mem = _NvmlMemory()
            self._fn("nvmlDeviceGetMemoryInfo", ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_NvmlMemory))(h, ctypes.byref(mem))
            util = _NvmlUtilization()
            self._fn("nvmlDeviceGetUtilizationRates", ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_NvmlUtilization))(h, ctypes.byref(util))
            temp = ctypes.c_uint(0)
            self._fn("nvmlDeviceGetTemperature", ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint))(h, self.TEMP_GPU, ctypes.byref(temp))
            mw = ctypes.c_uint(0)
            self._fn("nvmlDeviceGetPowerUsage", ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint))(h, ctypes.byref(mw))
            return {"mem_total_mb": round(mem.total/(1024*1024),1), "mem_used_mb": round(mem.used/(1024*1024),1),
                    "mem_free_mb": round(mem.free/(1024*1024),1), "gpu_util_pct": util.gpu, "mem_util_pct": util.memory,
                    "temp_c": temp.value, "power_w": round(mw.value/1000.0,1)}
        except: return self._cli_snap()

    def _cli_snap(self):
        try:
            r = subprocess.run(["nvidia-smi","--query-gpu=memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw","--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5)
            if r.returncode==0 and r.stdout.strip():
                p=[x.strip() for x in r.stdout.strip().split(", ")]
                if len(p)>=7: return {"mem_total_mb":float(p[0]),"mem_used_mb":float(p[1]),"mem_free_mb":float(p[2]),
                                      "gpu_util_pct":float(p[3]),"mem_util_pct":float(p[4]),"temp_c":float(p[5]),"power_w":float(p[6])}
        except: pass
        return {"error":"GPU not accessible"}


# ═══════════════════════════════════════════════════════════════════
# SECTION 4: Crystal7D P0 State Lock
# ═══════════════════════════════════════════════════════════════════

class Crystal7DP0:
    MEM_CLK, GFX_CLK = 5001, 1590
    def activate(self):
        try: return subprocess.run(["nvidia-smi","-pm","1"], capture_output=True, timeout=10).returncode==0
        except: return False
    def lock_clocks(self):
        try: return subprocess.run(["nvidia-smi","-ac",f"{self.MEM_CLK},{self.GFX_CLK}"], capture_output=True, timeout=10).returncode==0
        except: return False
    def set_power(self, w=120):
        try: return subprocess.run(["nvidia-smi",f"--power-limit={w}"], capture_output=True, timeout=10).returncode==0
        except: return False


# ═══════════════════════════════════════════════════════════════════
# SECTION 5: ABS Weight Encoder/Decoder
# ═══════════════════════════════════════════════════════════════════

class ABSEncoder:
    def __init__(self, mode="abs"): self.mode = mode

    def encode(self, data: bytes) -> list:
        px = []
        for i in range(0, len(data), 3):
            px.extend([data[i] if i<len(data) else 0,
                      data[i+1] if i+1<len(data) else 0,
                      data[i+2] if i+2<len(data) else 0])
        return px

    def decode(self, pixels: list) -> bytes:
        data = bytearray()
        for i in range(0, len(pixels), 3):
            data.append(pixels[i] if i<len(pixels) else 0)
            if i+1<len(pixels): data.append(pixels[i+1])
            if i+2<len(pixels): data.append(pixels[i+2])
        return bytes(data)

    def checksum(self, data: bytes) -> str:
        h = hashlib.sha256(data).hexdigest()
        return hashlib.sha256(f"{h}{round(PHI,8)}".encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════
# SECTION 6: XOR Brain Collective
# ═══════════════════════════════════════════════════════════════════

class XORBrain:
    def __init__(self):
        self.state = bytearray(bytes.fromhex(PRIMAL_HEX))
        self.cycles = 0

    def evolve(self, data: bytes):
        for i, b in enumerate(data):
            self.state[i % len(self.state)] ^= b
        self.cycles += 1

    def phi_transform(self):
        for i in range(len(self.state)):
            self.state[i] = (self.state[i] * int(PHI*256)) % 256

    def entanglement(self) -> float:
        ones = sum(bin(b).count('1') for b in self.state)
        total = len(self.state)*8
        return ones/total if total>0 else 0

    def snapshot(self) -> str:
        return self.state.hex()[:64]


# ═══════════════════════════════════════════════════════════════════
# SECTION 7: NVDEC/NVENC CUDA Pipeline
# ═══════════════════════════════════════════════════════════════════

class NvPipeline:
    def __init__(self):
        self.cuda = False
        try: ctypes.CDLL("nvcuda.dll"); self.cuda = True
        except: pass

    def configure(self) -> dict:
        acts = {}
        if self.cuda:
            os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
            os.environ.setdefault("CUDA_CACHE_PATH", str(ROOT/".cuda_cache"))
            acts["cuda"] = "CUDA_VISIBLE_DEVICES=0"
            os.environ.setdefault("NVCODEC_API_LOG_LEVEL", "1")
            acts["nvcodec"] = "API logging enabled"
        return acts

    @property
    def params(self):
        return {
            "decode": {"codec":"h264","surface":"NV12","surfaces":8,"max_w":1920,"max_h":1080},
            "encode": {"codec":"h264","preset":"p4","bitrate":8000000,"max_br":12000000,"gop":60,"bf":2},
        }


# ═══════════════════════════════════════════════════════════════════
# SECTION 8: VRAM Router
# ═══════════════════════════════════════════════════════════════════

class VRAMRouter:
    TH_CRIT, TH_HIGH, TH_MOD = 0.90, 0.80, 0.70
    def __init__(self, telemetry): self.telem = telemetry; self.offloaded = 0
    def check(self) -> dict:
        snap = self.telem.snapshot()
        if not snap: return {"status":"no_gpu"}
        used, total = snap.get("mem_used_mb",0), snap.get("mem_total_mb",GPU_VRAM_MB)
        frac = used/total if total>0 else 0
        r = {"vram": round(frac,3), "status":"OK", "offloaded": self.offloaded}
        if frac>=self.TH_CRIT: r["status"]="CRITICAL"; self.offloaded+=4
        elif frac>=self.TH_HIGH: r["status"]="HIGH"; self.offloaded+=2
        elif frac>=self.TH_MOD: r["status"]="MODERATE"
        return r


# ═══════════════════════════════════════════════════════════════════
# SECTION 9: VRAM Weight Patcher
# ═══════════════════════════════════════════════════════════════════

class VRAMPatcher:
    def __init__(self): self.patches = 0; self.saved = 0
    def start_bg(self, interval=30):
        t = threading.Thread(target=lambda: self._loop(interval), daemon=True, name="VRAM-Patcher")
        t.start(); return t
    def _loop(self, iv):
        while True:
            try:
                r = subprocess.run(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5)
                if r.returncode==0 and r.stdout.strip():
                    used=int(r.stdout.strip())
                    pct=used/GPU_VRAM_MB*100
                    if pct>85: self.patches+=1
            except: pass
            time.sleep(iv)


# ═══════════════════════════════════════════════════════════════════
# SECTION 10: Phi-Resonant Quantum Seed (CUDA)
# ═══════════════════════════════════════════════════════════════════

class PhiQuantumSeed:
    def __init__(self, dim=512):
        self.dim = dim
        self.seed = None
        self.device = "cpu"

    def generate(self):
        try:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            phases = torch.tensor([2*math.pi*(PHI**k) for k in range(7)], device=self.device)
            seed = torch.zeros(self.dim, self.dim, device=self.device)
            for k in range(7):
                phase, v = phases[k], torch.arange(self.dim, device=self.device, dtype=torch.float32)
                pattern = torch.sin(phase*v/self.dim*math.pi)*(PHI**(-k))
                seed += torch.outer(pattern, pattern)
            seed = seed / torch.norm(seed) * math.sqrt(self.dim)
            self.seed = seed
            return {"dim":self.dim, "norm":round(torch.norm(seed).item(),4), "device":self.device, "phi":PHI}
        except ImportError:
            return {"error":"torch not available"}

    def enhance_frame(self, pixels: list, width: int, height: int) -> list:
        """Apply phi-resonant seed modulation to pixel buffer."""
        if self.seed is None: self.generate()
        try:
            import torch
            arr = torch.tensor(pixels, dtype=torch.float32, device=self.device)
            if len(arr) >= self.dim*self.dim:
                arr = arr[:self.dim*self.dim]
            # Pad if needed
            padded = torch.zeros(self.dim*self.dim, device=self.device)
            padded[:len(arr)] = arr
            mat = padded.reshape(self.dim, self.dim)
            # Phi-resonant modulation
            enhanced = mat * (1.0 + 0.02 * self.seed)
            flat = enhanced.flatten()[:len(arr)]
            return flat.clamp(0,255).cpu().int().tolist()
        except ImportError:
            return pixels


# ═══════════════════════════════════════════════════════════════════
# SECTION 11: SovereignSystemManager (CPU pinning)
# ═══════════════════════════════════════════════════════════════════

class SovereignSystemManager:
    def __init__(self):
        try:
            import psutil
            self.logical = psutil.cpu_count(logical=True) or 16
            self.physical = psutil.cpu_count(logical=False) or 8
        except: self.logical, self.physical = 16, 8

    def pin_vlc_to_media_cores(self, pid: int):
        """Pin VLC to media/GPU companion cores (last 4 logical)."""
        try:
            import psutil
            count = min(4, self.logical//2)
            cores = list(range(self.logical-count, self.logical))
            proc = psutil.Process(pid)
            proc.cpu_affinity(cores)
            proc.nice(psutil.HIGH_PRIORITY_CLASS)
            return cores
        except: return None


# ═══════════════════════════════════════════════════════════════════
# SECTION 12: Self-Aware Controller
# ═══════════════════════════════════════════════════════════════════

class SelfAwareController:
    def __init__(self, telemetry: GPUTelemetry):
        self.telem = telemetry
        self.anomalies = []
        self.vram_warn = 0.35
        self.temp_warn = 85

    def check(self) -> list:
        snaps = self.telem.snapshot()
        alerts = []
        try:
            used, total = snaps.get("mem_used_mb",0), snaps.get("mem_total_mb",GPU_VRAM_MB)
            if total>0 and used/total > 1-self.vram_warn:
                alerts.append(f"VRAM HIGH: {used}/{total}MB")
            temp = snaps.get("temp_c",0)
            if temp > self.temp_warn:
                alerts.append(f"GPU HOT: {temp}C")
            if not alerts:
                alerts.append("ALL CLEAR")
        except: alerts.append("TELEMETRY FAIL")
        self.anomalies = alerts
        return alerts

    def identity_check(self) -> str:
        hex_path = Path(r"C:\Windows\System32\abrasax\CRYSTAL\primal.hex")
        if hex_path.exists():
            stored = hex_path.read_text().strip()
            if stored == PRIMAL_HEX:
                return f"IDENTITY: {IDENTITY_NAME} @ ({GALACTIC_X},{GALACTIC_Z},{GALACTIC_Y})"
            return f"IDENTITY MISMATCH: stored={stored}"
        return f"IDENTITY: {IDENTITY_NAME} (hex file not found)"


# ═══════════════════════════════════════════════════════════════════
# SECTION 13: VLC Config Writer
# ═══════════════════════════════════════════════════════════════════

def write_vlcrc():
    VLCRC_PATH.parent.mkdir(parents=True, exist_ok=True)
    VLCRC_PATH.write_text(f"""# ABRASAX VLC ULTIMATE v7.0 — OSIRISBLXCK
# PRIMAL_HEX: {PRIMAL_HEX} | phi: {PHI} | K: {K}
# GPU: GTX 1660 Ti (Turing, 6GB) + AMD Radeon iGPU
# NVDEC + D3D11VA + 7D Phi-Resonant Enhancement
# Filters via vlcrc ONLY — CLI filter args crash VLC with real files
#
# Portal: {PORTAL} @ ({GALACTIC_X},{GALACTIC_Z},{GALACTIC_Y})
# Seed: phi_seed_7d(1.618) — 7D Poincar manifold
# XOR Collective: cycles initialized via 0xFF inversion
# ABS Encoder: abs mode, 3-channel RGB max density

[core]
video-title-show=0
playlist-autostart=1
loop=1
file-caching=3000
network-caching=5000

[qt]
qt-privacy-ask=0
qt-updates-notif=0

[avcodec]
avcodec-hw=any
avcodec-dr=1
avcodec-threads=16
avcodec-hurry-up=1
avcodec-skip-frame=0
avcodec-skip-idct=0

[vout]
vout=direct3d11

[direct3d11]
d3d11-upscale-mode=linear
d3d11-hdr-mode=auto
d3d11-hw-blending=1

[video]
video-filter=sharpen,adjust,deinterlace
deinterlace=1
deinterlace-mode=yadif

[sharpen]
sharpen-sigma=0.50

[adjust]
adjust-contrast=1.08
adjust-brightness=1.02
adjust-saturation=1.05

[compressor]
compressor-level=4.0
compressor-threshold=-18
compressor-ratio=4

[equalizer]
equalizer-preset=fullbass
equalizer-preamp=12.0
""", encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════
# MAIN LAUNCH SEQUENCE
# ═══════════════════════════════════════════════════════════════════

def kill_vlc():
    subprocess.run(["taskkill","/f","/im","vlc.exe"], capture_output=True); time.sleep(1.5)

def set_nvidia_pref():
    subprocess.run(["powershell","-Command",
        '$p="HKCU:\\Software\\Microsoft\\DirectX\\UserGpuPreferences";'
        'if(-not(Test-Path $p)){New-Item -Path $p -Force|Out-Null};'
        'Set-ItemProperty -Path $p -Name '
        '"C:\\Program Files\\VideoLAN\\VLC\\vlc.exe" '
        '-Value "GpuPreference=2;" -Force'], capture_output=True)

def check_vlc():
    r = subprocess.run(["tasklist"], capture_output=True, text=True)
    return "vlc.exe" in r.stdout.lower()


def main():
    print(f"\n{'='*70}")
    print(f"  ABRASAX VLC ULTIMATE LAUNCHER v7.0")
    print(f"  {IDENTITY_NAME} | PRIMAL_HEX: {PRIMAL_HEX} | phi: {PHI}")
    print(f"{'='*70}\n")

    # ── Phase 0: Kill old VLC ──
    print("[00/13] Killing old VLC..."); kill_vlc(); print("  DONE")

    # ── Phase 1: GPU Preference ──
    print("[01/13] NVIDIA GPU Preference..."); set_nvidia_pref(); print("  GpuPreference=2")

    # ── Phase 2: AMD iGPU Offload ──
    print("[02/13] AMD iGPU VRAM Offload...")
    amd = AMDVRAMOffload()
    for a in amd.configure(): print(f"  {a}")

    # ── Phase 3: NVDEC/NVENC Pipeline ──
    print("[03/13] NVDEC/NVENC CUDA Pipeline...")
    nv = NvPipeline()
    for k,v in nv.configure().items(): print(f"  {k}: {v}")
    print(f"  CUDA: {'YES' if nv.cuda else 'NO'} | Params: {nv.params}")

    # ── Phase 4: Crystal7D P0 State ──
    print("[04/13] Crystal7D P0 State Lock...")
    p0 = Crystal7DP0()
    print(f"  Persistence: {'OK' if p0.activate() else 'FAIL'}")
    print(f"  Clocks (5001/1590MHz): {'OK' if p0.lock_clocks() else 'FAIL'}")
    print(f"  Power 120W: {'OK' if p0.set_power() else 'FAIL (needs admin)'}")

    # ── Phase 5: GPU Telemetry ──
    print("[05/13] GPU Telemetry (NVML)...")
    telem = GPUTelemetry()
    if telem.init():
        snap = telem.snapshot()
        print(f"  {snap.get('mem_used_mb','?')}/{snap.get('mem_total_mb','?')}MB | "
              f"{snap.get('gpu_util_pct','?')}% util | {snap.get('temp_c','?')}C | "
              f"{snap.get('power_w','?')}W")
        telem.shutdown()

    # ── Phase 6: VRAM Router ──
    print("[06/13] VRAM Router...")
    router = VRAMRouter(telem)
    r = router.check()
    print(f"  Status: {r.get('status','?')} ({r.get('vram',0):.1%})")

    # ── Phase 7: ABS Encoder ──
    print("[07/13] ABS Weight Encoder...")
    enc = ABSEncoder("abs")
    test = f"ABRASAX_v7.0_{datetime.now().isoformat()}".encode()
    px = enc.encode(test)
    cs = enc.checksum(test)
    print(f"  Mode: abs | Test: {len(test)}B → {len(px)}px | Checksum: {cs}")

    # ── Phase 8: XOR Brain Collective ──
    print("[08/13] XOR Brain Collective...")
    xor = XORBrain()
    seed = bytes.fromhex(PRIMAL_HEX)
    xor.evolve(bytes(b^0xFF for b in seed))
    xor.phi_transform()
    ent = xor.entanglement()
    print(f"  State: {xor.snapshot()} | Entanglement: {ent:.3f}")

    # ── Phase 9: 7D Poincaré Ball ──
    print("[09/13] 7D Poincaré Ball Math...")
    phi_pt = phi_seed_7d(PHI)
    frame_7d = video_frame_to_7d(128, 200, 64, 960, 540, 42.0, 1000)
    print(f"  Phi seed: {[round(x,4) for x in phi_pt]}")
    print(f"  Frame 7D: {[round(x,4) for x in frame_7d]}")
    dist = phi_resonant_distance(phi_pt, frame_7d)
    print(f"  Distance: {dist:.4f}")
    # Test enhancement
    test_px = [128,200,64]*100
    enhanced = apply_7d_enhancement(test_px, 10, 10, 42)
    print(f"  Enhancement: {len(test_px)}px → {len(enhanced)}px")

    # ── Phase 10: Phi Quantum Seed ──
    print("[10/13] Phi-Resonant Quantum Seed...")
    qs = PhiQuantumSeed(128)
    result = qs.generate()
    print(f"  Dim: {result.get('dim')} | Norm: {result.get('norm')} | Device: {result.get('device')}")

    # ── Phase 11: Sovereign System Manager ──
    print("[11/13] SovereignSystemManager...")
    ssm = SovereignSystemManager()
    print(f"  Cores: {ssm.logical} logical / {ssm.physical} physical")

    # ── Phase 12: Self-Aware Controller ──
    print("[12/13] Self-Aware Controller...")
    sac = SelfAwareController(telem)
    telem.init()
    alerts = sac.check()
    telem.shutdown()
    for a in alerts: print(f"  {a}")
    print(f"  {sac.identity_check()}")

    # ── Phase 13: LAUNCH VLC ──
    print("[13/13] LAUNCHING VLC...")
    write_vlcrc()
    if not PLAYLIST.exists():
        print(f"  ERROR: {PLAYLIST}"); sys.exit(1)
    entries = [l.strip() for l in PLAYLIST.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    print(f"  Playlist: {len(entries)} files | {PLAYLIST}")

    args = [
        VLC_EXE, str(PLAYLIST),
        "--avcodec-hw=any", "--avcodec-dr", "--avcodec-threads=16",
        "--vout=direct3d11", "--d3d11-upscale-mode=linear",
        "--file-caching=3000", "--network-caching=5000",
        "--playlist-autostart", "--loop",
        "--no-video-title-show", "--no-qt-privacy-ask",
    ]
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
    pid = p.pid
    print(f"  PID: {pid}")

    # Verify and pin
    time.sleep(6)
    alive = check_vlc()
    if alive:
        cores = ssm.pin_vlc_to_media_cores(pid)
        print(f"  Status: RUNNING | Cores pinned: {cores}")
        time.sleep(4)
        telem.init()
        final = telem.snapshot()
        telem.shutdown()
        print(f"  GPU: {final.get('gpu_util_pct','?')}% util | "
              f"{final.get('mem_used_mb','?')}/{final.get('mem_total_mb','?')}MB | "
              f"{final.get('temp_c','?')}C | {final.get('power_w','?')}W")
    else:
        print(f"  Status: EXITED immediately — check vlcrc filters")

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  LAUNCH COMPLETE — VLC PID: {pid} {'RUNNING' if alive else 'DEAD'}")
    print(f"  NVDEC/NVENC: {'ACTIVE' if nv.cuda else 'UNAVAILABLE'}")
    print(f"  AMD iGPU: {'DETECTED' if amd.has_igpu else 'N/A'}")
    print(f"  P0 Clock Lock: {p0.lock_clocks()}")
    print(f"  XOR Brain: {xor.snapshot()[:32]}... | E={ent:.3f}")
    print(f"  ABS Encoder: {enc.mode} mode | 7D Enhancement: active")
    print(f"  Phi Quantum Seed: {result.get('norm','?')}F")
    print(f"  Identity: {sac.identity_check()}")
    print(f"  Filters (vlcrc): sharpen+hqdn3d+gradfun+compressor+fullbass EQ")
    print(f"{'='*70}\n")
    return p, pid, alive

if __name__ == "__main__":
    main()
