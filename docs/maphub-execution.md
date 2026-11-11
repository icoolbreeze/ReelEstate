# map-hub 执行、TTS 与字幕（2026-10-12）

> **现行生产入口**：先读 [PRODUCTION.md](PRODUCTION.md)，运行 `npm run doctor`。xihu 测试工程已删除；新建使用 `templates/listing/episode.json`，旧 project.json 生产入口已移除。房源正式输出使用独立 `compliance.json`，缺少真实发布资料仍会阻断。

> **2026-10-24 架构入口更新**：先读 [architecture.md](architecture.md)。房源期改用 `projects/listing`，`projects/map-hub` 联接已于 2026-10-30 移除；正式期号由两类内容共用，`purpose: test` 不占号。Python 公共能力位于 `pipeline/common`，字体、标签防抖、跟踪、指引线、品牌和媒体组件位于 `templates/shared/remotion/src`。依赖只在 `tools/remotion` 管理，使用根目录 `npm run setup/typecheck/check/render/still`；旧命令继续兼容。原始素材不参与清理，渲染输出和 public 更新必须原子替换。其他制作与发布规则保持有效。
本页是开发与运行说明。现有视频的审美、发布和授权要求仍按 RUNBOOK 执行。

## 隔离工作目录
运行 `python pipeline/maphub/stage.py <EP>`，返回 `<EP>/work/remotion`。
每期的代码副本、public/data 链接属于本期，node_modules、字体和品牌素材共用。
不再切换共享模板的 public 或 src/episode；不要在共享模板目录运行成片渲染。
源代码更新后重新 stage 即可同步到本期。依赖统一在 tools/remotion 管理，根目录 npm run setup 准备模板和各期工作区。

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
真实房源还需要本期 compliance.json 通过原有合规检查；示例数据不构成发布许可。
输出放 out/，渲染成功后仍必须完成 RUNBOOK 的 LUFS、运动、至少四张静帧与人工审片，
不能把技术预检当作最终审美或发布确认。

## 验证
`python -B pipeline/maphub/test_workflow.py -v`。
在本期 work/remotion 运行 `npm run typecheck`。

## 标注、指引线与模板继承（强制）

1. **真实房源命名**：房源为真实数据时，地图卡片和室内标题直接用“客厅、卧室、厨房”等名称，不自动追加“样板间、示例房源、模拟房源”。示例内容必须显式设置 sampleData=true；房源身份与素材的后期处理信息分开记录，不因真实房源就把所有处理后素材称为原始实拍。preflight 会检查房间名称、clipTitles 和跟踪目标标签。
2. **两套标注都要验收**：地图固定标签与室内跟踪标注分别出慢推样片；不能只检查地图标签。移动文字与底板用共用 bakedLabel.tsx 的固定高分辨率图像绘制，等待 fonts.ts 导出的 fontsReady（真实 FontFace 注册完成）和图片解码，不能只等待 document.fonts.ready；中文、数字、拉丁字体分别用对应字符检查。连续帧还要核对同一标签的 raster 指纹，防止并行进程缓存回退字体。外层通过浮点 translate3d 定位；禁止逐帧改字号或用活字重绘代替位图移动。
3. **跟踪与素材时钟一致**：视频入点、mediaOffset、素材播放帧和标注关键帧时间统一。图片 Ken Burns 标注使用同一媒体播放时刻的 mediaGeom。切镜、蒙太奇和遮挡区段单独给 t0/t1，不跨切镜平滑。原始跟踪数据保留；在共享 annotationMotion.ts 中作有限像素修正与 C1 连续插值。任意帧、反向定位、并行渲染结果必须一致。
4. **标签位置稳定**：同一目标在整个出现区间选择固定的标签方位，避让标题、字幕、人物小窗及其他标签，不能每帧重新选择上下左右。入场动效放在独立内层，不能改变物体锚点。
5. **指引线规划**：使用共享 leaderRouting.ts；地理锚点保持原位，连线接到卡片/图标外缘，绕开房源头像、图片卡片、文字标签、人物窗口与字幕区。用整段镜头的几何采样选择固定参考路线和端口，避免逐帧选择最短路而左右换边。锚点被前景遮住时仍保留真实位置，让首段在前景下方自然遮挡，禁止把起点吸附到最近边缘。展开配套详情卡前先淡出对应旧连线，详情退场后再淡入。指引线先于前景卡片和头像绘制；不能以“放到图片上方”掩盖路径错误。无可用路径或不透明连线发生路线突变时，标注 QA 失败；调整布局，或将必要换路安排为先淡出旧线、全透明时换路、再淡入新线，地理锚点保持连续，然后重出样片。
6. **画面层级证据**：默认 MapHubHeygen 使用 `render_episode.py <EP> --draft --still <帧号> --ver <版本>` 会自动保存 .layers.json；不手工填写或沿用旧标注。完整素材和地图使用 world 层，人物小窗、卡片和标签使用 foreground 层；关键帧审美检查保存实际渲染边界与图像指纹。单一完整素材不能仅凭上方纹理被误判为第二层背景，两个大面积 world 层仍必须拦截。
7. **验收证据**：先检查跟踪原始点、平滑轨迹和素材物体的附着误差，再检查原始 PNG 与编码 MP4 中的字形/位移；不能只凭单帧小于 1px 或渲染成功判通过。对可见指引线记录实际路径与障碍碰撞，至少复核片头交接、一次室内跟踪、一次交通配套移动及片尾。对比图不替代连续帧审片。
8. **自动门槛**：`check_episode.py` 检查真实房源标注文案和跟踪数据；`render_episode.py` 在 stage 后自动运行 `check_overlay_motion.py`，验证共用轨迹、限幅、随机定位一致性与连线避让数学回归。可单独运行 `python pipeline/maphub/check_overlay_motion.py <EP>`。这些自动检查不能代替真实物体附着、连续帧和遮挡审片。
9. **共享代码的范围**：本系列公共修复统一修改 templates/shared/remotion/src，房源镜头编排修改 templates/map-hub/remotion/src，再由 stage.py 同步至单期 work/remotion/src。render_episode.py 会先 stage；新分期会继承共享修复，已存在的工作副本重新 stage 后继承，已经导出的 MP4 必须重新渲染。禁止只改工作副本。knowledge 等独立系列只在实际复用这些组件时继承，不能笼统声称所有系列自动修复。

