@echo off
rem Usage: scripts\voice\clone_tts_indextts25.cmd --episode <episode-dir> --script <narration.json>
python "%~dp0push_indextts25.py" %*
