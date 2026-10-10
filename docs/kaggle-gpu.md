# Kaggle 免费 GPU 外包（offload）

把吃显卡的 Python 任务放到 Kaggle 跑，结果下载回**当期**项目文件夹。驱动方：用户电脑上的 grok CLI。
操作清单见 `docs/TASK-kaggle.md`；脚本在 `scripts/kaggle/`。

## 1. 什么放 Kaggle，什么不放

| 任务 | 放哪 | 说明 |
|---|---|---|
| 人像抠像 RobustVideoMatting（`kernels/matting_rvm.py`） | **Kaggle** | 每段几秒到几十秒，T4 很快 |
| 精细逐帧抠像 BiRefNet | **Kaggle**（模板待加） | 慢，显存大 |
| 声音克隆 F5-TTS 批量（`kernels/tts_f5.py`） | **Kaggle** 或本地 1070 Ti | 本地 8 GB 也够；量大时放 Kaggle |
| 声音克隆 CosyVoice3 | 本地优先（`vendor/cosyvoice/`），需要时可写 Kaggle 模板 | |
| Remotion 合成 / 渲染 | **本地或 box，不上 Kaggle** | 用不上 GPU；Node、中文字体、素材往返都麻烦 |
| HeyGen 数字人、Muse 素材 | 云端 agent 负责 | 不在本流程内 |

抠像首选本地（docs/matting.md, scripts/matting/matte_local.cmd），Kaggle 为后备。

## 2. 额度

- GPU：2× T4（每块 15 GB 显存），或 P100。脚本默认 `--accelerator NvidiaTeslaT4`。
- 每周约 **30 小时** GPU；单次会话最长 **12 小时**；后台（commit）运行的 kernel 也计时。
- 数据集：单个私有数据集上限 ~100 GB，账户私有空间有限，用完要清。
- 每次 push 前确认剩余额度（kaggle.com → Settings / 右上角 Quota），不够就本地跑。
- 用完即停：kernel 跑完自动结束；不要开交互 notebook 挂机。

## 3. 每期独立（硬规则）

- **一期一个任务 = 一个私有数据集 + 一个私有 kernel**，slug：`reelestate-<episode>-<job>`。
  - `<episode>` = 项目文件夹名（如 `2026-10-03-lvcheng-2b1l`），`<job>` = `matting` / `tts` / …
  - slug 只用小写字母、数字、连字符，最长 50 字符（脚本自动截断并保证唯一后缀）。
- 数据集和 kernel **必须 private**（`is_private: true`），脚本强制。
- 输入只从当期文件夹取；输出只下载到 `projects/<category>/<episode>/kaggle/<job>/`，**绝不**写到其他期或仓库根目录。
- 当期的推送记录写在 `projects/<category>/<episode>/kaggle/<job>/job.json`（slug、时间、kernel 版本），便于重拉。
- 不跨期复用数据集；同一期同一任务重跑时更新同一个数据集新版本。

## 4. 认证（kaggle CLI）

- CLI：`kaggle`（用户电脑已装于 `%APPDATA%\Python\Python313\Scripts\kaggle.exe`）。
- 凭据：用户在 kaggle.com → Settings → API → *Create New Token* 下载 `kaggle.json`，放到 `C:\Users\<user>\.kaggle\kaggle.json`。新版 CLI 也认 `~/.kaggle/access_token` 或环境变量 `KAGGLE_USERNAME`/`KAGGLE_KEY`（或 `KAGGLE_API_TOKEN`）。
- **禁止**：打印、cat、复制、提交凭据文件或 key；不要把它放进仓库、日志、job.json、Kaggle 数据集。脚本只读取其中的 `username` 字段。
- 检查是否就绪（不泄露内容）：`python scripts/kaggle/push_job.py --check`。

## 5. 流程

```
push_job.py  → 打包输入 + job.json → 私有数据集(create/version) → 等就绪 → 推 GPU kernel
pull_job.py  → 轮询 kernel 状态 → complete 后下载输出到当期 kaggle/<job>/output/
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
