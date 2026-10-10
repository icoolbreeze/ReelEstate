# TASK：用 Kaggle GPU 跑抠像 / 声音克隆（给 grok）

规则全文：`docs/kaggle-gpu.md`。只做 GPU 任务；Remotion 渲染不上 Kaggle。不提交 git，不动 `.mcp.json`、`.grok/`。

1. **检查凭据**（不打印内容）：
   `python scripts/kaggle/push_job.py --check`
   报 `credentials: missing` → 停下，请用户把 `kaggle.json` 放到 `%USERPROFILE%\.kaggle\`。绝不打印/复制/提交它。
2. **确定当期**：`EP=projects/<category>/<episode>`（如 `projects/rental/2026-10-03-lvcheng-2b1l`）。输入只取该文件夹内文件。
3. **推送任务**：
   - 抠像：`python scripts/kaggle/push_job.py --episode %EP% --job matting --kernel matting_rvm --inputs %EP%/raw/avatar_01.mp4 %EP%/raw/avatar_02.mp4 --param format=prores`
   - 克隆：`python scripts/kaggle/push_job.py --episode %EP% --job tts --kernel tts_f5 --inputs voices/clone/ref.wav %EP%/audio/lines.json --param ref=ref.wav --param script=lines.json`
   - 先 `--dry-run` 看打包内容。
4. **等待并下载**：`python scripts/kaggle/pull_job.py --episode %EP% --job matting`（默认每 60 s 轮询，最长 3 h）。
   输出在 `%EP%/kaggle/<job>/output/`；失败时日志也会下载到那里，读 `*.log` 报告原因。
5. **汇报**：输出文件列表、时长、用掉的大致 GPU 时间。结果只留在当期文件夹。
