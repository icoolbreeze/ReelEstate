# NOTES — knowledge 系列做法迁移到房源类（map-hub）

来源：knowledge ep01-intro v5f（2026-10-16）。**已变成共用规范的条目统一见 `CONVENTIONS-shared.md`，本文件只保留指针和仍需在房源类确认的项。**本文件只列可迁移项，**不修改** `docs/RUNBOOK-map-hub-koubo.md`；采用前在 map-hub 流程里逐项确认。

## HeyGen / 主持人
1. **一次生成**：所有露脸段从定稿 VO 导出，首尾补 0.2s，按顺序拼成一条 `hg_ALL`（段间 0.6s 静音），记录段表（每段在 hg_ALL 内起止）。免费档 <60s，只生成一次。
2. **头部偏移核对**：export 音频与 hg_ALL 做互相关，得到恒定偏移（ep01 +0.023s）后再切。
3. **去水印复用干净帧**：同 look 同房间时，`heygen_mark.py` 的 `repair.png` 直接取已去水印 export 的一帧，不再调 flova。
4. **整条抠像**：对 `export_nomark.mp4` 跑一次 MatAnyone2，RGB 与 alpha 用同一参数切段。
5. **口型**：不做口型补偿（默认，2026-10-19 决定）：之前看到的不同步来自远程桌面播放；只有用户明确要求时才做 SyncNet 检查/平移。（若用户要求检查：SyncNet 负值=嘴早；mediapipe 开合法有偏置，别用。）
6. **切段公式**：`ss = 段起点 - 0.2 + 头部偏移`（SYNC 默认 0），帧数 = 画面段长度，不够用 `tpad clone`。参考 `projects/knowledge/ep01-intro/heygen/cut_v5.py`。

## 画面
7. 16:9 原始 plate 铺满 + 图形 + 抠像人物置顶（Room 分层），比 4:3 外扩更干净。
8. 字幕：去全部标点，深色半透明胶囊白字。
9. 照片优先，AI 图加「示意图」；生图前先网搜真实参考并记录 URL；统一暖色真实摄影风格，中国人面孔。
10. 卡片避开人脸/手/关键物；按每张图设卡片位置与 Ken Burns 焦点。
11. 多要点段落用「逐条占满画面 + 不同转场 + 最后 chip 收束」代替 PPT 网格。
12. 卡片实色/磨砂，背景不模糊；动效只用 video-shotcraft。
13. 平台角标留安全边距（right 44 / top 34）；片尾定格 1s。

## 配音 / 时间线
14. flova MiniMax passage 模式整稿一次（Gentle_Youth、1.1x、-16 LUFS），逐字时间重排 timeline；数字写汉字读法，字幕匹配时归一。
15. 画面段比音频早 6 帧开始（0.2s 引入），HeyGen 切段时要计入。

## 渲染
16. 同一工程用 props 出双平台版本：`--props=douyin.json` / `--props=shipinhao.json`，platform 同时控制角标与片尾关注胶囊。
17. 验收：ffprobe + 抽帧（角标/胶囊/无水印/无占位）。

## 输出目录
18. 房源视频也用同样的拆分：`out/release/` 只放最终交付（`<episode>_<platform>.mp4` + 封面 + 发布文案），测试片和检查片段放 `out/drafts/<ver>/`，旧版放 `out/archive/`，中间产物不进 `out/`。

## 已并入共用规范（见 CONVENTIONS-shared.md）
- 第 1–5 条（HeyGen 一次生成、头部偏移、去水印前置、整条抠像、口型不补偿）→ §3
- 第 8 条字幕、第 9 条照片优先与生图、第 12 条卡片与动效、第 13 条角标 → §4–6
- 第 14 条配音 → §2；第 16–17 条双平台渲染与验收 → §1、§8；第 18 条输出目录 → §1
## 仍需在房源类确认（版式类，由用户决定）
- 第 3 条：房源类用 `heygen_43.py`（4:3 外扩），复用干净帧需改为复用 `plate_43`。
- 第 6、15 条：房源类 `heygen_plan.py split` 的 `--sync` / `heygen_sync` 是可选项，默认 0（不补偿），见 CONVENTIONS-shared.md §3。
- 第 7、10、11 条：16:9 Room 分层、逐条占满画面的版式属于知识类，房源类是否采用由用户决定。
- 超分失败处理已统一（保留 lanczos 照常交付），见 CONVENTIONS-shared.md §7。
