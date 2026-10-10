@echo off
rem Usage: scripts\make-video.cmd ep08-xxx [stage]
rem Runs the map-hub runbook for projects\map-hub\<ep> as ONE headless grok job (resumable: re-run to continue).
rem Optional stage (listing|pois|script|voice|muse|annotate|heygen|matte|render|qa) runs only that stage.
if "%~1"=="" (echo usage: make-video ep08-xxx [stage] & exit /b 1)
set EP=projects\map-hub\%~1
if not exist "%~dp0..\%EP%\episode.yaml" (echo no %EP%\episode.yaml - run scripts\new_episode.cmd first & exit /b 1)
set ST=%~2
if "%ST%"=="" set ST=all
powershell -ExecutionPolicy Bypass -File "%~dp0make_video.ps1" -Ep "%EP%" -Stage "%ST%"
