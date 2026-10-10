@echo off
rem Usage: scripts\voice\clone_tts_f5.cmd path\to\script.json [--out DIR]
"%~dp0..\..\vendor\f5tts\.venv\Scripts\python.exe" "%~dp0clone_tts.py" --engine f5 %*
