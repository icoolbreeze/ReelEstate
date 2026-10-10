@echo off
rem Usage: scripts\new_episode.cmd --id ep08-xxx --category rental --listing ID_OR_URL [--footage DIR] [--title NAME]
python "%~dp0new_episode.py" %*
