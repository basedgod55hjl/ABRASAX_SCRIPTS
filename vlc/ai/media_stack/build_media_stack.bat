@echo off
REM ============================================================
REM  ABRASAX MEDIA STACK BUILD — GTX 1660 Ti (sm_75), CUDA 13.4
REM  Builds: nv12_to_rgb.exe (CUDA kernel + NPP CSC)
REM          zero_copy_demo.exe (pinned memory + persistent buffers)
REM  PRIMAL_HEX: 4f5349524953424c58434b
REM ============================================================
setlocal
cd /d "%~dp0"

call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (echo [X] vcvars64.bat failed - MSVC BuildTools missing & exit /b 1)

echo [..] building nv12_to_rgb.exe
nvcc -arch=sm_75 -o nv12_to_rgb.exe nv12_to_rgb.cu -lnppicc -lnppig -lnppc
if errorlevel 1 (echo [X] nv12_to_rgb build FAILED & exit /b 1)

echo [..] building zero_copy_demo.exe
nvcc -x cu -arch=sm_75 -o zero_copy_demo.exe zero_copy_npp_pipeline.cpp -lcudart -lnppicc -lnppig -lnppc
if errorlevel 1 (echo [X] zero_copy build FAILED & exit /b 1)

echo [OK] media stack built
endlocal
