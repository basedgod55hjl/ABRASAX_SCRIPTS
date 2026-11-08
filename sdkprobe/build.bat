@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (echo VCVARS_FAILED & exit /b 2)
cd /d C:\ABRASAX\SCRIPTS\sdkprobe
cl /nologo /W3 /O2 /DUNICODE /D_UNICODE sdkcheck.c /Fe:sdkcheck.exe dxguid.lib user32.lib gdi32.lib > cl.log 2>&1
if errorlevel 1 (echo BUILD_FAILED & type cl.log & exit /b 1)
echo BUILD_OK
