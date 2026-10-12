# map-hub 执行、TTS 与字幕（2026-10-12）
本页是开发与运行说明。现有视频的审美、发布和授权要求仍按 RUNBOOK 执行。

## 隔离工作目录
运行 `python pipeline/maphub/stage.py <EP>`，返回 `<EP>/work/remotion`。
每期的代码副本、public/data 链接属于本期，node_modules、字体和品牌素材共用。
不再切换共享模板的 public 或 src/episode；不要在共享模板目录运行成片渲染。
源代码更新后重新 stage 即可同步到本期。依赖仍在 templates/map-hub/remotion 安装一次。

## 后台执行器
`scripts\\make-video.cmd ep08-xxx [stage] [auto|claude|zcode|opencode|grok]`。
auto 的顺序为 Claude → ZCode → OpenCode，Grok 仅显式选择；也可设置进程环境变量 REEL_AGENT_EXECUTOR。
可通过 REEL_CLAUDE_BIN / REEL_ZCODE_BIN / REEL_OPENCODE_BIN 指定已安装的程序。
只在启动前检查可用性并选择执行器；任务启动后失败不换执行器、不重复消费外部额度。
日志、PID 和实际执行器写在本期 jobs/。`run_stage.ps1 -DryRun` 只检查选择，不启动。

## IndexTTS 主用，F5 备用
共享 presenter.yaml 的 voice → episode.yaml 的 presenter_override.voice → narration.json 全局字段 → 逐行字段。
HOOK、onCam=A/PIP 使用 speed_oncam，其余使用 speed_vo；显式 speed、seed 优先。
IndexTTS 上传入口解析上述配置并把实际参数保存为 voice/resolved_<run>.json。
单独情绪参考会随主参考上传，或用重复的 --emotion-ref 参数传入；同名不同文件会拒绝。
`--dry-run` 只显示参数，不写文件、不上传、不生成音频。

F5 是显式备用，不会自动在同一条片内换声音：
`scripts\\voice\\clone_tts_f5.cmd <EP>/voice/narration.json --episode <EP> --out <EP>/voice/f5`。
F5 和 IndexTTS 都输出按行 id 命名的 wav，再使用相同的对齐与合成入口。
不要将缺失克隆音频交给 Edge 自动补齐；Edge 仅用于全片草稿与时长估算。

## 真实音频时间戳
已有本机 Whisper small 模型可使用：
`vendor\\cosyvoice\\.venv\\Scripts\\python.exe pipeline/asr/align_voice.py --script <resolved-narration.json> --voice-dir <normalized-wav-dir> --backend whisper --model <existing-small.pt> --device cuda`。
默认使用 fp32；不下载模型。可另选已安装的 faster-whisper 和本地模型目录。
必须对齐最终用于合成的 wav，裁静音或响度处理后需要重新对齐。
每个 <id>.json 包含 text、audio_sha256、words[{t,s,e}]。
转写不匹配或时间无效时只写 <id>.review.json 并返回 2，不能自动把识别错词当成通过。
听过后可校正词文本；词时间必须仍对应真实音频。禁止修改音频指纹来接受过期结果。

逐字字幕按实际词起止时间排列。字幕概括了口播时，在脚本行中给出 `cap_spans`，
每项为 [start,end]（去标点、空格并进行 NFKC 规范化后的字符区间）。
例如口播“你好，世界”，字幕“问候”，可明确给出 `cap_spans:[[0,4]]`。
未给区间时，概括字幕的比例估算只允许用于 --draft。

`python pipeline/maphub/build_vo.py <EP> --voice-dir <normalized-wav-dir>`。
默认采用 episode.yaml 的 script；缺 wav、缺时间戳、过期音频指纹会停止。
`--alignment-dir <dir>` 可单独指定时间戳目录；`--draft` 明确允许估算字幕。
重做配音后重新 plan HeyGen；超过本期 oncam_budget_s 时不会输出上传音频。

## 成片入口与检查
`python pipeline/maphub/check_episode.py <EP> --heygen`
`python pipeline/maphub/render_episode.py <EP>`
草稿使用 --draft。单帧使用 --still <frame>。
检查脚本包括稿件和音频指纹、字幕范围、素材缺失/占位、HeyGen 计划版本及预算、hook alpha。
真实房源还需要本期 project.json 通过原有合规检查；示例数据不构成发布许可。
输出放 out/，渲染成功后仍必须完成 RUNBOOK 的 LUFS、运动、至少四张静帧与人工审片，
不能把技术预检当作最终审美或发布确认。

## 验证
`python -B pipeline/maphub/test_workflow.py -v`。
在本期 work/remotion 运行 `npm run typecheck`。
