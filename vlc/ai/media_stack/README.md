# ABRASAX MEDIA STACK — scripts + grounded adoptability

Source: NotebookLM `vlc-7d-cuda-kernels` full-script generation, 2026-10-03.
Host: GTX 1660 Ti 6GB (sm_75, **no Tensor Cores**) + Ryzen 7 4800H (Vega iGPU) + CUDA 13.4 + MSVC BuildTools.

## Contents
| File | What | Built/tested on this host |
|---|---|---|
| `nv12_to_rgb.cu` | NV12→RGB: custom CUDA kernel + NPP `nppiNV12ToBGR709CSC` (limited-range BT.709 fix) | ✅ compiled + ran |
| `zero_copy_npp_pipeline.cpp` | Pinned host memory (`cudaHostAlloc`) + persistent buffers, 0 allocs in-loop | ✅ compiled + ran |
| `rife_vulkan_pipeline.py` | RIFE frame interpolation wrapper (`--scale=0.5` 4K OOM fix, `-j 2:2:2` caps) | ⏳ needs `rife-ncnn-vulkan` portable binary |
| `tensorrt_video_engine.cpp` | TRT 10.x: `enqueueV3` + `setTensorAddress` + `CUDA_MODULE_LOADING=LAZY` | ⏸ TensorRT runtime not installed |

## Grounded adoptability (notebook Q1/Q2, verified against this box)

| Component | VRAM cost | Concurrent with loaded LLM (~300 MB free)? |
|---|---|---|
| NV12→RGB CUDA/NPP | ~10–30 MB | ✅ YES |
| rife-ncnn-vulkan (Vulkan → CPU/iGPU) | 0 MB dGPU | ✅ YES (`-g 1` iGPU or `-g -1`) |
| Pinned zero-copy staging | ~5–15 MB | ✅ YES |
| TensorRT engine | 300 MB–1.5 GB | ⚠️ NO — needs ≥500 MB free, unload first |
| PyTorch/CUDA RIFE | ~3 GB (1080p) | ❌ solo only, ≥3.2 GB free |

**Minimal subset first (value per MB):** NV12→RGB + rife-ncnn-vulkan (offloaded) + pinned staging reuse.
**Mid-pipeline fallbacks:** persistent staging buffer reuse; `--scale=0.5`; CPU/Vulkan fallback; `CUDA_MODULE_LOADING=LAZY`.

## Build recipes
```bat
:: NV12→RGB demo  (or just run build_media_stack.bat)
nvcc -arch=sm_75 -o nv12_to_rgb.exe nv12_to_rgb.cu -lnppicc -lnppig -lnppc

:: Zero-copy pinned pipeline
nvcc -x cu -arch=sm_75 -o zero_copy_demo.exe zero_copy_npp_pipeline.cpp -lcudart -lnppicc -lnppig -lnppc

:: RIFE (after downloading the portable release)
python rife_vulkan_pipeline.py frames_in frames_out
```

Notes:
- `nppGetStreamContext()` full init added (CUDA 12+ requirement) — plain zeroed `NppStreamContext` may fail.
- `tensorrt_video_engine.cpp`: upstream script had `argv[14]`/`argv` bugs — fixed to `argv[1]`/`argv[0]`.
