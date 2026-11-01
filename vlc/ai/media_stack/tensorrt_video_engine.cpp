// tensorrt_video_engine.cpp
// ABRASAX media stack — TensorRT 10.x execution pipeline (enqueueV3 + setTensorAddress + LAZY loading).
// Source: NotebookLM "vlc-7d-cuda-kernels" script generation, 2026-10-03 (argv bug fixed).
// STATUS on this host: TensorRT runtime NOT installed — script kept for when an engine exists.
// VRAM: base engine weights + ~100 MB workspace; CUDA_MODULE_LOADING=LAZY trims peak.
// Build: cl /EHsc /O2 /I"%TENSORRT_ROOT%\include" tensorrt_video_engine.cpp /link /LIBPATH:"%TENSORRT_ROOT%\lib" nvinfer.lib cudart.lib

#include <iostream>
#include <fstream>
#include <vector>
#include <memory>
#include <cstdlib>
#include <cuda_runtime.h>
#include <NvInfer.h>

#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            std::cerr << "CUDA Error: " << cudaGetErrorString(err) << std::endl; \
            exit(EXIT_FAILURE); \
        } \
    } while (0)

class Logger : public nvinfer1::ILogger {
public:
    void log(Severity severity, const char* msg) noexcept override {
        if (severity <= Severity::kWARNING) {
            std::cout << "[TRT] " << msg << std::endl;
        }
    }
} gLogger;

int main(int argc, char** argv) {
#if defined(_WIN32)
    _putenv("CUDA_MODULE_LOADING=LAZY");
#else
    setenv("CUDA_MODULE_LOADING", "LAZY", 1);
#endif
    std::cout << "[Init] CUDA_MODULE_LOADING=LAZY enabled (reduces peak startup VRAM)." << std::endl;

    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <path_to_engine_file.engine>" << std::endl;
        return 0;
    }
    std::string enginePath = argv[1];

    std::ifstream file(enginePath, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        std::cerr << "[Error] Failed to open engine file: " << enginePath << std::endl;
        return -1;
    }

    size_t size = file.tellg();
    file.seekg(0, std::ios::beg);
    std::vector<char> engineData(size);
    file.read(engineData.data(), size);
    file.close();

    std::cout << "[VRAM Budget] TensorRT engine file size: "
              << (size / (1024.0 * 1024.0)) << " MB" << std::endl;

    std::unique_ptr<nvinfer1::IRuntime> runtime(nvinfer1::createInferRuntime(gLogger));
    std::unique_ptr<nvinfer1::ICudaEngine> engine(
        runtime->deserializeCudaEngine(engineData.data(), size));

    if (!engine) {
        std::cerr << "[Error] Engine deserialization failed! Check VRAM availability." << std::endl;
        return -1;
    }

    std::unique_ptr<nvinfer1::IExecutionContext> context(engine->createExecutionContext());
    if (!context) {
        std::cerr << "[Error] Failed to create execution context." << std::endl;
        return -1;
    }

    cudaStream_t stream;
    CUDA_CHECK(cudaStreamCreate(&stream));

    int32_t numTensors = engine->getNbIOTensors();
    std::vector<void*> deviceBuffers;
    std::cout << "[TRT 10.x] Setting tensor addresses via setTensorAddress():" << std::endl;

    for (int i = 0; i < numTensors; ++i) {
        const char* tensorName = engine->getIOTensorName(i);
        nvinfer1::TensorIOMode ioType = engine->getTensorIOMode(tensorName);
        nvinfer1::Dims dims = engine->getTensorShape(tensorName);
        nvinfer1::DataType dataType = engine->getTensorDataType(tensorName);

        size_t vol = 1;
        for (int d = 0; d < dims.nbDims; ++d) {
            vol *= (dims.d[d] > 0 ? (size_t)dims.d[d] : 1);
        }
        size_t elementSize = (dataType == nvinfer1::DataType::kFLOAT) ? 4 : 2;
        size_t bufferSize = vol * elementSize;

        void* d_ptr = nullptr;
        CUDA_CHECK(cudaMalloc(&d_ptr, bufferSize));
        deviceBuffers.push_back(d_ptr);
        context->setTensorAddress(tensorName, d_ptr);

        std::cout << "  - Tensor: " << tensorName
                  << " | " << (ioType == nvinfer1::TensorIOMode::kINPUT ? "INPUT" : "OUTPUT")
                  << " | " << (bufferSize / 1024.0) << " KB" << std::endl;
    }

    std::cout << "[Inference] Enqueuing execution via enqueueV3()..." << std::endl;
    bool status = context->enqueueV3(stream);
    if (!status) {
        std::cerr << "[Error] enqueueV3 failed!" << std::endl;
    } else {
        CUDA_CHECK(cudaStreamSynchronize(stream));
        std::cout << "[Success] TensorRT inference completed." << std::endl;
    }

    CUDA_CHECK(cudaStreamDestroy(stream));
    for (void* ptr : deviceBuffers) {
        CUDA_CHECK(cudaFree(ptr));
    }
    return 0;
}
