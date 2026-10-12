# ASR 与字幕时间戳

map-hub 已实现本地 Whisper / faster-whisper 词级时间戳入口：`pipeline/asr/align_voice.py`。
只加载已有本地模型，不自动下载。输出绑定音频 SHA256；转写不匹配时写 review.json 并退出。
安装环境、命令和字幕区间格式见 `docs/maphub-execution.md`。

通用 project.json 流水线的自动 ASR → narration.segments 仍待实现。
