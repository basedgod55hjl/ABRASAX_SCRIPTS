# Loki pipeline report

Generated 2026-10-10 21:20:55

Iterations: 2

## Iteration 1  (2026-10-10 21:19:21 -> 2026-10-10 21:19:46)

### GPUs

- Device 0 selected: NVIDIA GeForce GTX 1660 Ti (discrete) (0x2191)

### Video: NVIDIA enhance -> AMD Radeon final output

| preset | ms | bytes | note |
|---|---:|---:|---|
| amd_final_nvidia_enhanced | 1436 | 2825144 | NVIDIA decodes + scale_cuda 2x, AMD Vega performs the FINAL encode |
| amd_final_libplacebo | 3386 | 2688941 | libplacebo upscale ON the Vega iGPU, AMD final encode |
| amd_final_cpu_denoise | 600 | 2439423 | CPU hqdn3d denoise, AMD final encode (fastest full path) |
| nvidia_reference | 954 | 3382275 | all-NVIDIA reference: decode + scale_cuda + NVENC |

### Verify: 6/9

- [x] video:amd_final_nvidia_enhanced — 2825144 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-amd_final_nvidia_enhanced.mp4
- [x] video:amd_final_libplacebo — 2688941 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-amd_final_libplacebo.mp4
- [x] video:amd_final_cpu_denoise — 2439423 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-amd_final_cpu_denoise.mp4
- [x] video:nvidia_reference — 3382275 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-nvidia_reference.mp4
- [ ] nvcc:vlc_yuv_kernels.cubin — vlc_yuv_kernels.cu
c1xx: fatal error C1083: Cannot open source file: 'vlc_yuv_kernels.cu': No such file or directory
C
- [ ] nvcc:vlc_yuv_kernels.ptx — vlc_yuv_kernels.cu
c1xx: fatal error C1083: Cannot open source file: 'vlc_yuv_kernels.cu': No such file or directory
C
- [ ] nvcc:harness — harness_vlc_yuv.cu
c1xx: fatal error C1083: Cannot open source file: 'harness_vlc_yuv.cu': No such file or directory
C
- [x] rust:abrasax_7d_core — 282 ms
- [x] rust:cuda_node — 517 ms

## Iteration 1  (2026-10-10 21:20:25 -> 2026-10-10 21:20:55)

### GPUs

- GPU listing:
- Device 0 selected: NVIDIA GeForce GTX 1660 Ti (discrete) (0x2191)

### Video: NVIDIA enhance -> AMD Radeon final output

| preset | ms | bytes | note |
|---|---:|---:|---|
| amd_final_nvidia_enhanced | 1115 | 2825144 | NVIDIA decodes + scale_cuda 2x, AMD Vega performs the FINAL encode |
| amd_final_libplacebo | 3209 | 2688941 | libplacebo upscale ON the Vega iGPU, AMD final encode |
| amd_final_cpu_denoise | 597 | 2439423 | CPU hqdn3d denoise, AMD final encode (fastest full path) |
| nvidia_reference | 941 | 3382275 | all-NVIDIA reference: decode + scale_cuda + NVENC |

### Verify: 10/10

- [x] video:amd_final_nvidia_enhanced — 2825144 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-amd_final_nvidia_enhanced.mp4
- [x] video:amd_final_libplacebo — 2688941 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-amd_final_libplacebo.mp4
- [x] video:amd_final_cpu_denoise — 2439423 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-amd_final_cpu_denoise.mp4
- [x] video:nvidia_reference — 3382275 bytes -> C:\Users\sirch\Desktop\ABRASAX_GOD_OS\agents\ABRASAX_SCRIPTS\vlc\streamout\tmph42d67ie-nvidia_reference.mp4
- [x] nvcc:vlc_yuv_kernels.cubin — 6241 ms
- [x] nvcc:vlc_yuv_kernels.ptx — 5684 ms
- [x] nvcc:harness — 8636 ms
- [x] kernel:execute — RESULT: PASS
- [x] rust:abrasax_7d_core — 273 ms
- [x] rust:cuda_node — 516 ms
