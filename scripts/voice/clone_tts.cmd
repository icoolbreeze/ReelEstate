@echo off
rem Usage: scripts\voice\clone_tts.cmd path\to\script.json [--out DIR] [--fp16]
"%~dp0..\..\vendor\cosyvoice\.venv\Scripts\python.exe" "%~dp0clone_tts.py" %*
