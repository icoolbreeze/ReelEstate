@echo off
setlocal
rem Knowledge 口播 series entry (projects/knowledge). The map-hub listing pipeline is scripts\make-video.cmd.
rem Usage: scripts\make-knowledge-video.cmd ep01-intro [all|voice|heygen-plan|matte|compose|render] [--check] [--draft] [--force]
if "%~1"=="" (echo usage: make-knowledge-video ep01-intro [step] [--check] [--draft] [--force] & exit /b 1)
set "SELF=%~dp0"
set "EP=%~1"
set "ST=all"
set "REST="
:parse
shift
if "%~1"=="" goto run
echo %~1 | findstr /b /c:"--" >nul
if errorlevel 1 (set "ST=%~1") else (set "REST=%REST% %~1")
goto parse
:run
python "%SELF%..\pipeline\knowledge\make_video.py" "%EP%" --step "%ST%" %REST%
exit /b %ERRORLEVEL%
