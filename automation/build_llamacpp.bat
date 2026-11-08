@echo off
setlocal
set ROOT=C:\ABRASAX\BUILD\llamacpp
set CMAKE="C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
set GIT="C:\Program Files\Git\cmd\git.exe"

call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (echo VCVARS_FAILED & exit /b 2)
echo [1/4] env ready

if not exist "%ROOT%" mkdir "%ROOT%"
cd /d "%ROOT%"
if not exist src\.git (
  echo [2/4] cloning llama.cpp
  %GIT% clone --depth 1 https://github.com/ggml-org/llama.cpp src > clone.log 2>&1
  if errorlevel 1 (echo CLONE_FAILED & type clone.log & exit /b 3)
) else (
  echo [2/4] src present
)

echo [3/4] configuring (CUDA on, examples on)
%CMAKE% -S src -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_SERVER=ON > configure.log 2>&1
if errorlevel 1 (
  echo CONFIGURE_FAILED_RETRY_NO_NINJA
  %CMAKE% -S src -B build -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_SERVER=ON > configure2.log 2>&1
  if errorlevel 1 (echo CONFIGURE_FAILED & type configure2.log & exit /b 4)
  echo [4/4] building VS generator
  %CMAKE% --build build --config Release --target llama-server llama-mtmd-cli -j 8 > build.log 2>&1
) else (
  echo [4/4] building Ninja
  %CMAKE% --build build --target llama-server llama-mtmd-cli -j 8 > build.log 2>&1
)
if errorlevel 1 (echo BUILD_FAILED & exit /b 5)
echo BUILD_OK
dir /b /s build\bin\llama-server.exe build\bin\Release\llama-server.exe 2>nul
exit /b 0
