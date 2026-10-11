# Kaggle 免费 GPU 外包（offload）

把吃显卡的 Python 任务放到 Kaggle 跑，结果下载回**当期**项目文件夹。驱动方：用户电脑上的 grok CLI。
操作清单见 `docs/TASK-kaggle.md`；脚本在 `scripts/kaggle/`。

## 1. 什么放 Kaggle，什么不放

| 任务 | 放哪 | 说明 |
|---|---|---|
| 人像抠像 RobustVideoMatting（`kernels/matting_rvm.py`） | **Kaggle** | 每段几秒到几十秒，T4 很快 |
| 精细逐帧抠像 BiRefNet | **Kaggle**（模板待加） | 慢，显存大 |
| 声音克隆 F5-TTS 批量（`kernels/tts_f5.py`） | **Kaggle** 或本地 1070 Ti | 本地 8 GB 也够；量大时放 Kaggle |
| 视频超分 SeedVR2 V9（`kernels/seedvr2_v9.py`） | **Kaggle** | 一条 1280×720、24fps 的片 → 1920×1080，双 T4。Remotion 渲染不上 Kaggle |
| 声音克隆 CosyVoice3 | 本地优先（`vendor/cosyvoice/`），需要时可写 Kaggle 模板 | |
| Remotion 合成 / 渲染 | **本地或 box，不上 Kaggle** | 用不上 GPU；Node、中文字体、素材往返都麻烦 |
| HeyGen 数字人、Muse 素材 | 云端 agent 负责 | 不在本流程内 |

抠像首选本地（docs/matting.md, scripts/matting/matte_local.cmd），Kaggle 为后备。

## 2. 额度

- GPU：2× T4（每块 15 GB 显存），或 P100。脚本默认 `--accelerator NvidiaTeslaT4`。
- 每周约 **30 小时** GPU；单次会话最长 **12 小时**；后台（commit）运行的 kernel 也计时。
- 并发：交互式 GPU 会话最多 1 个；后台（commit / `kernels push`）GPU 会话最多 2 个，可以同时跑。两条视频就是两个后台会话。两个会话同时跑时，周额度按会话分别计时（各跑 1 小时扣 2 小时）。
- 浏览器里开着的交互式 GPU 笔记本占掉那 1 个交互名额，CLI 推送会排队。开后台任务前先关掉它。
- Kaggle 若因「预计会超出每周 GPU 额度」拒绝启动，停下并报告原文，不要反复重推。
- 数据集：单个私有数据集上限 ~100 GB，账户私有空间有限，用完要清。
- 每次 push 前确认剩余额度（kaggle.com → Settings / 右上角 Quota），不够就本地跑。
- 用完即停：kernel 跑完自动结束；不要开交互 notebook 挂机。

## 3. 每期独立（硬规则）

- **一个并行会话 = 一个私有数据集 + 一个私有 kernel**。slug：`reelestate-<episode>-<job>[-<run>]`。
  - `<episode>` = 项目文件夹名（如 `2026-10-03-lvcheng-2b1l`），`<job>` = `matting` / `tts` / `upscale` / …
  - 一条视频输入会自动得到 `<run>`（由相对路径算出，同一文件稳定、不同文件不同）。多文件任务（抠像、克隆）默认共用一个槽；要并行再显式加 `--run`。
  - slug 只用小写字母、数字、连字符，最长 50 字符（脚本按完整 slug 做哈希后缀，两个 run 不会截成同一个）。
- 数据集和 kernel **必须 private**（`is_private: true`），脚本强制。
- 输入只从当期文件夹取。输出只下载到该 run 自己的目录：`projects/<category>/<episode>/kaggle/<job>/<run>/output/`（没有 run 的旧任务仍在 `kaggle/<job>/output/`）。**绝不**写到其他 run、其他期或仓库根目录。
- 推送记录写在该 run 的 `job.json`。同一个 run 的 kernel 还在排队或运行时，再次 push 会直接退出，不改数据集、不改 `job.json`、不碰已有输出。
- 不跨期复用数据集。同一 run 跑完后重跑，才更新这个 run 自己的数据集。

## 4. 认证（kaggle CLI）

- CLI：`kaggle`（用户电脑已装于 `%APPDATA%\Python\Python313\Scripts\kaggle.exe`）。
- 凭据：用户在 kaggle.com → Settings → API → *Create New Token* 下载 `kaggle.json`，放到 `C:\Users\<user>\.kaggle\kaggle.json`。新版 CLI 也认 `~/.kaggle/access_token` 或环境变量 `KAGGLE_USERNAME`/`KAGGLE_KEY`（或 `KAGGLE_API_TOKEN`）。
- **禁止**：打印、cat、复制、提交凭据文件或 key；不要把它放进仓库、日志、job.json、Kaggle 数据集。脚本只读取其中的 `username` 字段。
- 检查是否就绪（不泄露内容）：`python scripts/kaggle/push_job.py --check`。

## 5. 流程

```
push_job.py  → 打包输入 + job.json → 私有数据集(create/version) → 等就绪 → 推 GPU kernel
pull_job.py  → 轮询该 run 的 kernel → complete 后只下载到该 run 的 output/
```

kernel 内：输入在 `/kaggle/input/<slug>/`，参数在其中的 `job.json`，输出写 `/kaggle/working/out/`。
kernel 需要联网（`enable_internet`）以 pip 安装依赖、下载模型权重——这要求 Kaggle 账号已完成手机验证。

## 6. 任务模板

### matting_rvm（RobustVideoMatting）
- 输入：一个或多个视频（`--inputs a.mp4 b.mp4`）。
- 输出（每个视频）：`<name>_rgba.mov`（ProRes 4444 带 alpha，Remotion `<OffthreadVideo transparent>` 可用）
  和/或 `<name>_png/%05d.png` 序列；外加 `<name>_alpha.mp4`（灰度遮罩，便于检查）。
- 参数：`--param format=prores|png|both`（默认 prores）、`--param model=mobilenetv3|resnet50`（默认 resnet50）、`--param downsample=0.25`（1080p 推荐 0.25，4K 0.125）。

### tts_f5（F5-TTS 批量克隆）
- 输入：脚本 JSON + 参考 wav（+ 参考文本）。
- 脚本 JSON：`{"ref_text": "...", "lines": [{"id": "L01", "text": "..."}, ...]}`（也接受顶层数组；
  也认 `voices/clone/test_script.json` 的 `id`/`text` 字段）。
- 参数：`--param ref=ref.wav`、`--param script=lines.json`、`--param speed=1.0`、`--param nfe=32`。
- 输出：`<id>.wav`（24 kHz）+ `manifest.json`。
- 声音克隆仅限用户本人且有声音授权（`consent/`）。

### seedvr2_v9（SeedVR2 V9，视频超分）

本项目的视频超分只用这个内核。它替代临时的 RealESRGAN notebook 和更早的 SeedVR2 预览脚本。那些历史结果留在原地，不用删。

- 推送：`python scripts/kaggle/push_job.py --episode <ep> --job upscale --kernel seedvr2_v9 --inputs <一条 1280x720 24fps 的 mp4>`
- 下载：`python scripts/kaggle/pull_job.py --episode <ep> --job upscale --run <run>`（`<run>` 以 push 打印的为准；该 job 底下只有一个 run 时可以省略）
- 成片：`<ep>/kaggle/upscale/<run>/output/out/seedvr2_1080p.mp4`，旁边有 `out/report.json`。`pull_job.py` 只把这一次 kernel 的 working 目录拉到这个 run 的 `output/`。
- 可选参数只有两个：`--param run_mode=full|preview`（默认 `full`），`--param validate_frames=33`（默认 33；写 0 表示跳过校验）。`preview` 在校验之后最多处理 120 帧。其它 `--param` 会让内核直接退出。
- 源片必须是 1280×720、24fps。别的分辨率或帧率会失败。输出是 1920×1080，原音轨按流拷贝，播放速度不变。每次只推一条视频。
- 内核要联网，用来克隆上游仓库并下载权重。加速器保持默认 `NvidiaTeslaT4`（一次会话两张 T4）。后台可以同时跑两个这样的会话，用来并行处理两条视频。每条视频一个 run、一个 kernel、一份本地输出。浏览器里的交互式 GPU 笔记本会占掉唯一的交互名额，推送前先关掉。
- 已经测过的参数不要改：3B FP16、batch 9、tile 256 / overlap 32、BlockSwap 24、批与批重叠 0、两张卡接缝重叠 3 帧、不传 `--cuda_device`。
