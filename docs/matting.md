# 人像抠像（matting）

**本地默认 MatAnyone2**（用户电脑 GTX 1070 Ti，由 grok CLI 执行）；MatAnyone2 不可用（包装不上、权重下载失败、无 CUDA、推理报错/显存不足）时**自动回退 RobustVideoMatting（RVM）**；本地不可用、显存不够或批量很大时，**再退到 Kaggle**（`docs/kaggle-gpu.md`，`scripts/kaggle/kernels/matting_rvm.py`）。

## 本地

- 引擎：默认 `matanyone2`，自动回退 `rvm`。命令不变：
  `scripts\matting\matte_local.cmd projects\<cat>\<ep>\avatar\clip1.mp4 [--out DIR]`
- 运行环境：复用 `vendor/cosyvoice/.venv`（已有 torch+CUDA），只需 torch、numpy、Pillow、系统 ffmpeg；MatAnyone2 包用该 venv 的 pip 从 GitHub 安装（`pip install "git+https://github.com/pq-yang/MatAnyone2"`），权重放 `vendor/matanyone2/pretrained_models/`（gitignore，首次运行自动下载，不入库）。
- MatAnyone2 需要首帧 mask：默认用 RVM resnet50 跑第一帧、alpha 二值化，在输出目录写 `<stem>_mask.png`；自带 mask 时传 `--mask some.png`。
- 参数：
  - `--engine matanyone2|rvm`（默认 `matanyone2`）；`--engine rvm` 只跑原来的 RVM 流程。
  - `--max-size 1080`（MatAnyone2，默认）：按原宽高比将推理短边上限设为 1080；1920×1080 原尺寸推理，3840×2160 按 1920×1080 推理，720p 输入不放大。输出仍保持输入分辨率；4K 输出的 alpha 是推理遮罩插值回原尺寸，不代表 4K 原生抠像。1070 Ti（Pascal，8 GB）不开 fp16。
  - 命令行默认值、知识类入口缺省值和公共 presenter 的 `matting.max_size` 统一为 1080。显式 `--max-size` 或配置覆盖仍有效；720 仅用于显式选择的低分辨率测试，不自动降到 720。现有的 MatAnyone2 失败回退 RVM 策略保留，并输出实际引擎与原因；要求必须使用 MatAnyone2 时传 `--no-fallback`。新默认仅作用于后续抠像，已有缓存需显式重跑；不自动重渲染历史成片。
  - `--mask MASK.png`：指定首帧二值 mask（只能配合单个输入）。
  - `--no-fallback`：失败时不回退 RVM，直接非零退出。
  - RVM 专用：`--model resnet50|mobilenetv3`、`--downsample`（1080p 用 0.4，4K 用 0.125）、`--fp16`（Pascal 不要开）。
- 实际跑了哪个引擎会打印 `engine: matanyone2` 或 `engine: rvm (fallback: <原因>)`。每次还会写 `<stem>_report.json`：请求引擎、实际引擎、回退原因、输入/推理/输出尺寸、帧数和耗时。`matanyone2_passed` 只在实际引擎是 MatAnyone2 且没有回退原因时为 true。回退到 RVM 必须记为未通过，不能报成 MatAnyone2 成功。
- 显存不足时保持报错原文。不会自动把 `max_size` 从 1080 降到 720。要更低分辨率必须显式传入 `--max-size`，并在会客厅配置里写 `max_size_explicit: true`。
- 小ONE会客厅只抠已确认的剪辑范围加手柄，不抠整场采访。同一连续镜头保持抠像状态，切镜头重置；超长镜头分块时带暖机重叠，输出再裁掉暖机。椅子和桌子要么明确丢掉，要么另给家具遮罩，不靠人像模型自动判断。没有真人素材时只核对尺寸和调用链，不把色块渲染说成 1080p 抠像通过。HeyGen 成片仍是 720p，不先放大再抠。
- 输出与以前完全一样（默认写到 `<ep>/matte/`，每期独立，视频文件已被 gitignore）：
  - `<stem>_rgba.mov` — ProRes 4444 + alpha（剪辑母版）
  - `<stem>_alpha.webm` — VP9 + alpha（Remotion：`<OffthreadVideo src=... transparent />`）
  - `<stem>_check.mp4` — 灰度遮罩，检查边缘用
  - `<stem>_mask.png` — 首帧 seed mask（仅 MatAnyone2 路径）

## 分层用法（字在人后）
原视频做背景 → 中间放文字/图片 → 最上层放抠出的人（webm alpha）。不需要纯色背景。换引擎不改分层。

## 何时用 Kaggle
- 本地 GPU 被占用（如正在跑声音克隆）或片段总长很长；
- 需要 BiRefNet 逐帧精抠（显存大、慢）。
