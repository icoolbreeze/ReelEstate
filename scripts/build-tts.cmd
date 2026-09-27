@echo off
rem ============================================================
rem  Build qwen-tts.exe from vendor\qwentts.cpp with CUDA.
rem  Based on upstream buildcuda.cmd; changed:
rem   - uses VS 2022 Professional vcvars64.bat (upstream hardcodes BuildTools 2022)
rem   - CMAKE_CUDA_ARCHITECTURES=61 (GTX 1070 Ti = Pascal sm_61)
rem  Output: vendor\qwentts.cpp\build\Release\qwen-tts.exe (or build\ with Ninja)
rem
rem  Fallbacks if CUDA build fails:
rem   - Vulkan: replace -DGGML_CUDA=ON ... with -DGGML_VULKAN=ON (needs Vulkan SDK),
rem             see upstream buildvulkan.cmd
rem   - CPU only: drop the GGML_CUDA / CUDA_ARCHITECTURES flags entirely (slow)
rem ============================================================
setlocal

set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo [build-tts] vcvars64.bat not found: %VCVARS%
  echo [build-tts] Edit VCVARS in scripts\build-tts.cmd to match your Visual Studio install.
  exit /b 1
)
call "%VCVARS%"

cd /d "%~dp0..\vendor\qwentts.cpp"
if not exist CMakeLists.txt (
  echo [build-tts] vendor\qwentts.cpp is empty. Run: git submodule update --init --recursive
  exit /b 1
)

rem rd /s /q build 2>nul
mkdir build 2>nul
cd build

cmake .. -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=61
if errorlevel 1 exit /b 1
cmake --build . --config Release -j %NUMBER_OF_PROCESSORS%
if errorlevel 1 exit /b 1

cd ..
echo [build-tts] Done. Look for build\Release\qwen-tts.exe or build\qwen-tts.exe
endlocal
