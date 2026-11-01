// nv12_to_rgb.cu
// ABRASAX media stack — NV12 -> RGB GPU conversion (CUDA kernel + NPP CSC paths)
// Source: NotebookLM "vlc-7d-cuda-kernels" script generation, 2026-10-03.
// Build: nvcc -arch=sm_75 -o nv12_to_rgb.exe nv12_to_rgb.cu -lnppicc -lnppig -lnppc
// VRAM budget: ~4.5 MB for a 1080p frame (1.5 MB NV12 + 3.0 MB RGB). Safe under 50 MB.

#include <cuda_runtime.h>
#include <npp.h>
#include <iostream>
#include <vector>
#include <cstdlib>

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            std::cerr << "CUDA Error at " << __FILE__ << ":" << __LINE__ \
                      << " - " << cudaGetErrorString(err) << std::endl; \
            exit(EXIT_FAILURE); \
        } \
    } while (0)

#define NPP_CHECK(call) \
    do { \
        NppStatus status = call; \
        if (status != NPP_SUCCESS) { \
            std::cerr << "NPP Error at " << __FILE__ << ":" << __LINE__ \
                      << " - Status Code: " << status << std::endl; \
            exit(EXIT_FAILURE); \
        } \
    } while (0)

// Custom CUDA kernel: NV12 (BT.709 limited range) -> packed RGB (8-bit)
__global__ void nv12_to_rgb_kernel(const uint8_t* __restrict__ y_plane,
                                   const uint8_t* __restrict__ uv_plane,
                                   uint8_t* __restrict__ rgb_out,
                                   int width, int height, int y_pitch, int uv_pitch, int rgb_pitch) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x >= width || y >= height) return;

    float Y = static_cast<float>(y_plane[y * y_pitch + x]);

    // NV12 chroma is 2x2 subsampled and interleaved (U even, V odd)
    int uv_x = (x / 2) * 2;
    int uv_y = y / 2;
    int uv_index = uv_y * uv_pitch + uv_x;

    float U = static_cast<float>(uv_plane[uv_index]) - 128.0f;
    float V = static_cast<float>(uv_plane[uv_index + 1]) - 128.0f;

    // BT.709 limited range: Y in [16,235] -> [0,255]
    float Y_norm = (Y - 16.0f) * (255.0f / 219.0f);
    if (Y_norm < 0.0f) Y_norm = 0.0f;

    float R = Y_norm + 1.5748f * V;
    float G = Y_norm - 0.1873f * U - 0.4681f * V;
    float B = Y_norm + 1.8556f * U;

    int r_out = __float2int_rn(fminf(fmaxf(R, 0.0f), 255.0f));
    int g_out = __float2int_rn(fminf(fmaxf(G, 0.0f), 255.0f));
    int b_out = __float2int_rn(fminf(fmaxf(B, 0.0f), 255.0f));

    int rgb_index = y * rgb_pitch + x * 3;
    rgb_out[rgb_index + 0] = static_cast<uint8_t>(r_out);
    rgb_out[rgb_index + 1] = static_cast<uint8_t>(g_out);
    rgb_out[rgb_index + 2] = static_cast<uint8_t>(b_out);
}

int main() {
    const int width = 1920;
    const int height = 1080;
    const size_t y_size = width * height;
    const size_t uv_size = width * (height / 2);
    const size_t nv12_total_size = y_size + uv_size;
    const size_t rgb_size = width * height * 3;

    std::cout << "[VRAM Allocation] Allocating ~4.5 MB on GPU for 1080p frame buffers..." << std::endl;

    uint8_t *d_nv12 = nullptr, *d_rgb_custom = nullptr, *d_bgr_npp = nullptr;
    CUDA_CHECK(cudaMalloc(&d_nv12, nv12_total_size));
    CUDA_CHECK(cudaMalloc(&d_rgb_custom, rgb_size));
    CUDA_CHECK(cudaMalloc(&d_bgr_npp, rgb_size));

    // Synthetic NV12: Y=128, U=128, V=128
    CUDA_CHECK(cudaMemset(d_nv12, 128, y_size));
    CUDA_CHECK(cudaMemset(d_nv12 + y_size, 128, uv_size));

    // --- Path 1: custom CUDA kernel ---
    dim3 blockSize(32, 16);
    dim3 gridSize((width + blockSize.x - 1) / blockSize.x, (height + blockSize.y - 1) / blockSize.y);

    uint8_t* d_y_plane = d_nv12;
    uint8_t* d_uv_plane = d_nv12 + y_size;

    std::cout << "[Path 1] Executing Custom CUDA NV12->RGB Kernel..." << std::endl;
    nv12_to_rgb_kernel<<<gridSize, blockSize>>>(d_y_plane, d_uv_plane, d_rgb_custom,
                                                 width, height, width, width, width * 3);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    // --- Path 2: NPP CSC (limited-range BT.709 -> full-range BGR) ---
    std::cout << "[Path 2] Executing NPP nppiNV12ToBGR709CSC_8u_P2C3R_Ctx..." << std::endl;

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

    const Npp8u* pSrc[2] = { d_y_plane, d_uv_plane };
    int rSrcStep = width;
    Npp8u* pDst = d_bgr_npp;
    int nDstStep = width * 3;
    NppiSize oSizeROI = { width, height };

    // 709CSC handles limited-range (16-235) BT.709 inputs -> full-range BGR
    NPP_CHECK(nppiNV12ToBGR_709CSC_8u_P2C3R_Ctx(pSrc, rSrcStep, pDst, nDstStep, oSizeROI, nppCtx));
    CUDA_CHECK(cudaStreamSynchronize(stream));

    std::cout << "[Success] Both NV12 conversion paths executed successfully!" << std::endl;

    CUDA_CHECK(cudaStreamDestroy(stream));
    CUDA_CHECK(cudaFree(d_nv12));
    CUDA_CHECK(cudaFree(d_rgb_custom));
    CUDA_CHECK(cudaFree(d_bgr_npp));

    return 0;
}
