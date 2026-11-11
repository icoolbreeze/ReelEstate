# 流程建议：知识类口播「一句话出片」

> 目标：用户只说一句 **「做知识视频 epNN + 脚本」**，Agent 按固定阶段跑到底，中途只停 2 次确认。
> 共用规范（输出目录、配音、数字人、字幕角标、视觉、Kaggle、质检、封面、合规）见 `docs/CONVENTIONS-shared.md`，本方案只写知识类流程。
> 参照 map-hub 的 `new_episode.cmd + episode.yaml`。本文只是建议，脚本还没写。依据是 ep01-intro v5f 实际跑通的做法（见 `docs/RUNBOOK-knowledge-koubo.md`）。

## 1. 阶段（按顺序）

| # | 阶段 | 输入 → 输出 | 工具 / 脚本 | 耗时 | 积分 |
|---|---|---|---|---|---|
| 0 | **建期** | 选题 + 脚本 → `projects/knowledge/epNN-<slug>/episode.yaml` | `new-knowledge-episode.cmd`（已有，需扩字段） | 1 分钟 | 0 |
| 1 | **脚本校验** | episode.yaml → 校验报告（通过才继续） | `knowledge_lint.py`（新） | 1 分钟 | 0 |
| 2 | **配音 + 时间轴** | 脚本 → `vo/Sxx.wav` + 逐字时间 → `timeline.json` | flova MiniMax passage（Gentle_Youth，1.1x，-16 LUFS）+ `vo_to_timeline.py`（新） | 5 分钟 | 每句 ≤10，全片约 60–80 |
| 3 | **全屏分配** | timeline → 露脸段表（自动凑满 <57s） | `oncam_plan.py`（新） | 即时 | 0 |
| 4 | **关键帧** | 模板 + timeline → 每段 1 张 still | `remotion still`（批量脚本 `keys.py` 新） | 5 分钟 | 0 |
| ⏸ | **确认 #1** | 用户看关键帧 + 稿 + 露脸段表 | — | — | — |
| 5 | **素材生成** | 场景描述 → `public/broll/epNN/*`、封面底图 | Muse（box 浏览器，先网搜参考）/ flova gpt-image-2.5-flare；`cover/gen_bg.py` | 20–40 分钟 | 每图约 12，封面 24 |
| 6 | **HeyGen 一次生成** | 露脸段 → `hg_ALL.wav`（0.6s 间隔）→ `heygen/export.mp4` | `hg_concat.py`（新）+ box 浏览器操作 HeyGen（Cool Breeze / "Professional in suit on sofa"，上传音频，免费 720p） | 15–40 分钟 | HeyGen 额度（≤60s） |
| 7 | **去水印 / 抠像 / 切段** | export → `heygen169/HG_*.mp4 + _alpha.webm` | `heygen_mark.py`（复用干净帧）→ `matte_local.py`（MatAnyone2）→ `cut_v5.py` 通用化（默认 lanczos 720p→1080p；超分仅在用户明确要求时做）（SYNC 默认 0，不做口型补偿） | 10 分钟 | 0 |
| 8 | **整片抖音测试** | → `out/drafts/<ver>/epNN_test_douyin.mp4` | `remotion render --props=douyin.json` | 4 分钟 | 0 |
| ⏸ | **确认 #2** | 用户看整片（提醒：远程桌面会造成假性不同步） | — | — | — |
| 9 | **视频号版 + 封面** | → `out/release/<episode>_douyin.mp4`、`<episode>_shipinhao.mp4`、`cover_3x4.png / cover_4x3.png` | `--props=shipinhao.json`；`KnowledgeCover3x4/4x3` | 5 分钟 | 0 |
| 10 | **交付 + 发布文案** | → `out/release/`（两版视频、两张封面、`publish.md`：描述、短标题 ≤16 字、话题 3–5 个） | `deliver.py`（新） | 2 分钟 | 0 |

**episode.yaml 字段（建议）：**
- `title`, `slug`, `series_ep`
- `script`：分段 S01..Snn，每段 `text` 与 `scene`（版式类型：oncam / cards / cinematic / map / end）
- `facts`：每个数字的来源链接和日期
- `platforms: [douyin, shipinhao]`
- `oncam`：可选，手动指定露脸段；不填则自动分配
- `assets`：每个场景的图片描述和参考关键词
- `cover`：`lines`, `hl`, `sub`
- `stages`：每阶段的 status，支持断点续跑

**输出目录约定：** 见 `CONVENTIONS-shared.md` §1（`out/release/` 交付、`out/drafts/<ver>/` 测试、`out/archive/` 旧版）。

## 2. 用户确认点（只有 2 个，可选第 3 个）
1. **关键帧 + 稿 + 露脸段**（花 HeyGen 额度和生图积分之前）。
2. **整片抖音版**（出视频号版和封面之前）。
3. （可选）**封面文字**：默认用 `cover.lines`，用户不改就直接出。

## 3. 已自动化 vs 待补
**已有：**
- `new-knowledge-episode.cmd`（需扩字段）
- flova TTS / 生图（`mcp_call.py`、`flova_minimax_tts.py`）
- `heygen_mark.py`、`matte_local.py`
- Remotion 工程 `KnowledgeKoubo`：intro C、S05 电影化、片尾、平台 props
- 封面模板 `Cover.tsx` + `gen_bg.py`
- `cut_v5.py`（目前写死 ep01 的段表）

**待补（估计工作量）：**
- `knowledge_lint.py`：来源、禁词「最/第一/唯一/——/--」、时长（目标 ≤100s）——0.5 天
- `vo_to_timeline.py`：TTS 输出 → timeline.json，含数字归一、去标点字幕——0.5 天
- `oncam_plan.py`：按段优先级凑露脸 <57s——0.5 天
- `hg_concat.py`：段落导出、补静音、hg_ALL 和段表——0.3 天
- `cut_heygen.py`：由 cut_v5 通用化，读段表、头部偏移（SYNC 默认 0）——0.3 天
- `keys.py` / `deliver.py`：批量关键帧、交付打包、发布文案草稿——0.5 天
- `make-knowledge-video.cmd`：串起以上阶段，支持 `--check` 干跑和断点续跑——0.5 天
- 版式按 episode.yaml 的 `scene` 数据驱动（目前 ep01 场景写在 tsx 里）——1–2 天，**最大一块**

合计约 **4.5–5.5 人天**。

## 4. 失败回退
- **flova 余额不足**：按余额轮换 kid3/5/6/7；带参考图时用 count=1；只清理 0 余额账号。TTS 全部失败时按策略回退本地 F5，不出无声版。
- **超分（可选，见 CONVENTIONS-shared.md §7）**：默认不做，用 lanczos 把 720p 放大到 1080p（用户可接受）。只有用户明确要求时才走 Kaggle 超分，按用户的队列策略：任务处于 QUEUED 就取消并重新提交，最多 10 次；仍然失败就停止超分这一步，保留 lanczos 版本，并在报告里注明。
- **HeyGen**：
  - 免费 720p，右下角水印：同 look 用 `heygen_mark.py` 复用干净帧；换 look 才调 flova 修补。
  - 口型：不做口型补偿（默认，2026-10-19 决定）：之前看到的不同步来自远程桌面播放；只有用户明确要求时才做 SyncNet 检查/平移。
  - 额度不足或界面受阻：停下，写 `heygen/BLOCKED.md`，露脸段先用旧片段占位并标「占位」，不出正式片。
- **Muse 不可用**：改用 flova gpt-image-2.5-flare（同一套暖色真实摄影提示词，配网搜参考图），图上标「示意图」。

## 5. 每期预算（约 100s 成片）
- **flova：** 配音 60–80 + 生图 6–10 张约 70–120 + 封面 24，合计约 **150–220 积分**（重试另计，单张不重复跑）。
- **HeyGen：** 一次生成，**≤57s**（ep01 为 49.7s），免费档 1 条。
- **Agent 时间：** 无人值守约 1.5–2 小时，加 2 次用户确认。

## 6. 和房源类（map-hub）的关系
- **独立：** 编号、目录、episode.yaml 和流水线都分开；知识类没有 listing、POI、地图步骤。map-hub 的文件只读。
- **共享：**
  - Cool Breeze 和已保存的 look、干净帧
  - 品牌 logo 库、video-shotcraft 动效、字体、字幕胶囊样式
  - `heygen_mark.py`、`matte_local.py`、平台 props
  - 封面模板思路
- 可迁移清单见 `docs/NOTES-knowledge-to-listing.md`。
