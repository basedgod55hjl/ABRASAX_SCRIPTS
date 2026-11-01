// zero_copy_npp_pipeline.cpp
// ABRASAX media stack — pinned host memory (cudaHostAlloc) + persistent buffers,
// zero VRAM re-allocation in the playback loop.
// Source: NotebookLM "vlc-7d-cuda-kernels" script generation, 2026-10-03 (NPP ctx init fixed).
// Build: nvcc -x cu -arch=sm_75 -o zero_copy_demo.exe zero_copy_npp_pipeline.cpp -lcudart -lnppicc -lnppig -lnppc
// VRAM budget: persistent ~9.3 MB for 1080p (3.1 MB NV12 + 6.2 MB BGR). 0 dynamic allocs in-loop.

#include <cuda_runtime.h>
#include <npp.h>
#include <iostream>
#include <vector>
#include <cstring>
#include <cstdlib>

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            std::cerr << "CUDA Error: " << cudaGetErrorString(err) << std::endl; \
            exit(EXIT_FAILURE); \
        } \
    } while (0)

#define NPP_CHECK(call) \
    do { \
        NppStatus status = call; \
        if (status != NPP_SUCCESS) { \
            std::cerr << "NPP Error: " << status << std::endl; \
            exit(EXIT_FAILURE); \
        } \
    } while (0)

int main() {
    const int width = 1920;
    const int height = 1080;
    const size_t nv12_bytes = width * height * 3 / 2; // 1080p NV12 ~3.1 MB
    const size_t bgr_bytes = width * height * 3;      // 1080p BGR  ~6.2 MB

    std::cout << "[Init] Allocating Pinned Host Memory (cudaHostAlloc) for zero-copy streaming..." << std::endl;

    uint8_t *h_pinned_nv12 = nullptr;
    uint8_t *h_pinned_bgr = nullptr;

    CUDA_CHECK(cudaHostAlloc(&h_pinned_nv12, nv12_bytes, cudaHostAllocMapped | cudaHostAllocWriteCombined));
    CUDA_CHECK(cudaHostAlloc(&h_pinned_bgr, bgr_bytes, cudaHostAllocMapped));

    memset(h_pinned_nv12, 128, nv12_bytes);

    std::cout << "[VRAM Budget] Pre-allocating persistent device buffers (~9.3 MB total VRAM)..." << std::endl;
    uint8_t *d_nv12 = nullptr, *d_bgr = nullptr;
    CUDA_CHECK(cudaMalloc(&d_nv12, nv12_bytes));
    CUDA_CHECK(cudaMalloc(&d_bgr, bgr_bytes));

    cudaStream_t stream;
    CUDA_CHECK(cudaStreamCreate(&stream));

    // Application-managed NppStreamContext (CUDA 13.x documented pattern).
    NppStreamContext nppCtx = {};
    nppCtx.hStream = stream;
    cudaGetDevice(&nppCtx.nCudaDeviceId);
    cudaDeviceProp props;
    cudaGetDeviceProperties(&props, nppCtx.nCudaDeviceId);
    nppCtx.nMultiProcessorCount               = props.multiProcessorCount;
    nppCtx.nMaxThreadsPerMultiProcessor       = props.maxThreadsPerMultiProcessor;
    nppCtx.nMaxThreadsPerBlock                = props.maxThreadsPerBlock;
    nppCtx.nSharedMemPerBlock                 = props.sharedMemPerBlock;
    nppCtx.nCudaDevAttrComputeCapabilityMajor = props.major;
    nppCtx.nCudaDevAttrComputeCapabilityMinor = props.minor;
    cudaStreamGetFlags(stream, &nppCtx.nStreamFlags);
    nppCtx.hWorkspace = 0; // no optional workspace cache

    // NPP plane pointers for NV12 (plane 0 = Y, plane 1 = interleaved UV)
    const Npp8u* pSrc[2] = { d_nv12, d_nv12 + (width * height) };
    int rSrcStep = width;
    Npp8u* pDst = d_bgr;
    int nDstStep = width * 3;
    NppiSize oSizeROI = { width, height };

    const int num_frames = 100;
    std::cout << "[Loop] Executing " << num_frames << " frames with 0 VRAM reallocations..." << std::endl;

    for (int frame = 0; frame < num_frames; ++frame) {
        CUDA_CHECK(cudaMemcpyAsync(d_nv12, h_pinned_nv12, nv12_bytes, cudaMemcpyHostToDevice, stream));
        NPP_CHECK(nppiNV12ToBGR_709CSC_8u_P2C3R_Ctx(pSrc, rSrcStep, pDst, nDstStep, oSizeROI, nppCtx));
        CUDA_CHECK(cudaMemcpyAsync(h_pinned_bgr, d_bgr, bgr_bytes, cudaMemcpyDeviceToHost, stream));
    }

    CUDA_CHECK(cudaStreamSynchronize(stream));
    std::cout << "[Success] Processed " << num_frames << " video frames with 0 VRAM allocation stalls." << std::endl;

    CUDA_CHECK(cudaStreamDestroy(stream));
    CUDA_CHECK(cudaFree(d_nv12));
    CUDA_CHECK(cudaFree(d_bgr));
    CUDA_CHECK(cudaFreeHost(h_pinned_nv12));
    CUDA_CHECK(cudaFreeHost(h_pinned_bgr));

    return 0;
}
