@echo off
rem Agent runs this. The user gives a 选题 (knowledge 口播 series, projects/knowledge, own numbering from ep01).
rem Folder is epNN-pinyin. Topic/title/city stay in episode.yaml. No listing id, no map/POI files.
rem Usage: scripts\new-knowledge-episode.cmd --slug gongjijin --topic 公积金新政解读 [--title 片名] [--city 成都]
python "%~dp0..\pipeline\knowledge\new_episode.py" %*
