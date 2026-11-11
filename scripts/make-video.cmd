@echo off
rem Usage: scripts\make-video.cmd ep08-xxx [stage] [auto|claude|zcode|opencode|grok]
if "%~1"=="" (echo usage: make-video ep08-xxx [stage] [executor] & exit /b 1)
set "EP=projects\listing\%~1"
if not exist "%~dp0..\%EP%\episode.yaml" (echo missing episode.yaml & exit /b 1)
set "ST=%~2"
if "%ST%"=="" set "ST=all"
set "EX=%~3"
if "%EX%"=="" set "EX=auto"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_video.ps1" -Ep "%EP%" -Stage "%ST%" -Executor "%EX%"
exit /b %ERRORLEVEL%
