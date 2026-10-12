@echo off
rem Agent runs this. The user gives a listing id, or a new-home 楼盘 name.
rem Folder is epNN-pinyin. Category stays in episode.yaml.
rem Rental/resale: scripts\new_episode.cmd --category rental --slug xihu --listing ID --title 小区名
rem New-home has no listing id: scripts\new_episode.cmd --category new-home --slug xipai --title 楼盘名
rem Knowledge: scripts\new_episode.cmd --category knowledge --slug yuedu --topic 选题
python "%~dp0new_episode.py" %*
