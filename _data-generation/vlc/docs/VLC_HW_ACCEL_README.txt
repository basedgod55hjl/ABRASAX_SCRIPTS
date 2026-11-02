========================================
VLC ULTIMATE HARDWARE ACCELERATION GUIDE
OSIRISBLXCK / ABRASAX God OS
System: AMD Ryzen 7 4800H + NVIDIA GTX 1660 Ti
========================================

HARDWARE DETECTED:
├── CPU: AMD Ryzen 7 4800H (8C/16T) @ 2.9GHz
├── GPU1: NVIDIA GeForce GTX 1660 Ti (6GB VRAM)
├── GPU2: AMD Radeon(TM) Graphics (iGPU)
└── Display: Multi-monitor (4 displays)

VERSION: VLC 3.0.23 (Vetinari)

HW ACCELERATION MODULES:
├── D3D11VA (Direct3D11 Video Acceleration)
├── DXVA2 (DirectX Video Acceleration 2)
├── OpenGL (OpenGL rendering)
├── WGL (Windows OpenGL)
├── FFmpeg (Software codecs + HW bridge)
└── NVENC via FFmpeg (Hardware encoding)

LAUNCH SCRIPTS (on Desktop):
├── VLC_HW_ACCEL_MAX.bat — Launch with MAX GPU acceleration
├── VLC_NVENC_ENCODE.bat — Hardware encoding with NVENC
└── VLC_HW_ACCEL_TEST.bat — Interactive test suite

CONFIG: %%APPDATA%%\vlc\vlcrc (permanent HW config)

RECOMMENDED LAUNCH:
    vlc.exe --avcodec-hw=any --vout=direct3d11 \\
         --d3d11va --dxva2 --codec=all

NVENC ENCODE:
    vlc.exe input.mp4 --sout=#transcode{vcodec=h264,\\
         venc=nvenc,vb=20000}:standard{mux=mp4,\\
         dst=output.mp4,access=file} --play-and-exit

GPU MONITORING:
    nvidia-smi --query-gpu=utilization.gpu,memory.used,\\
         temperature.gpu,power.draw --format=csv
