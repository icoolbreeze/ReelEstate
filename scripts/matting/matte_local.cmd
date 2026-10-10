@echo off
rem Local person matting. Default engine MatAnyone2, automatic fallback to RobustVideoMatting.
rem Usage: scripts\matting\matte_local.cmd IN.mp4 [more.mp4] [--out DIR] [--engine matanyone2 or rvm] [--mask M.png] [--no-fallback]
setlocal
set "REPO=%~dp0..\.."
set "PY=%REPO%\vendor\cosyvoice\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%REPO%\scripts\matting\matte_local.py" %*
