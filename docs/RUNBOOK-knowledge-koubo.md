# RUNBOOK — knowledge 口播 series (end to end)

> **现行生产入口**：先读 [PRODUCTION.md](PRODUCTION.md)，运行 `npm run doctor`。xihu 测试工程已删除；新建使用 `templates/listing/episode.json`，旧 project.json 生产入口已移除。房源正式输出使用独立 `compliance.json`，缺少真实发布资料仍会阻断。

> **2026-10-24 架构入口更新**：先读 [architecture.md](architecture.md)。房源期改用 `projects/listing`，`projects/map-hub` 联接已于 2026-10-30 移除；正式期号由两类内容共用，`purpose: test` 不占号。Python 公共能力位于 `pipeline/common`，字体、标签防抖、跟踪、指引线、品牌和媒体组件位于 `templates/shared/remotion/src`。依赖只在 `tools/remotion` 管理，使用根目录 `npm run setup/typecheck/check/render/still`；旧命令继续兼容。原始素材不参与清理，渲染输出和 public 更新必须原子替换。其他制作与发布规则保持有效。

知识/政策/市场分析类口播（`projects/knowledge/epNN-<slug>`），与房源类独立编排、共用基础能力和正式发布编号：
没有 listing、POI、地图步骤。账号 @贝壳-TV（视频号）/ @贝壳TV（抖音），主持人小ONE（HeyGen 数字人 Cool Breeze）。

> **先读 [`CONVENTIONS-shared.md`](CONVENTIONS-shared.md)**：输出目录与命名、配音、数字人、字幕角标、视觉、素材生成、Kaggle、质检、封面、合规等共用规范在那里，本文件只写知识类独有的流程和命令。

## 本类型独有（知识类）
- 画幅 **16:9 1920x1080**（房源类为 4:3 1440x1080）；露脸段用原始 16:9 HeyGen 画面 + `heygen_mark.py` 去水印（不做 4:3 外扩）。
- 露脸段**全屏**，不用 PiP（`SHOW_PIP=false`）；露脸段：开场自我介绍、判断标准、委托/服务说明、结尾「我是小ONE……」。
- 没有 listing、POI、地图步骤；内容是选题，事实来源写 `script/research.md`。
- 版式：Intro C 名片、S05 式「逐条占满画面」电影化讲解、贝壳图标片尾（「小ONE」手绘下划线）。
- 自我介绍「我是小ONE，你的房产顾问」，结尾以「我是小ONE」开头（HeyGen 结尾段从这里切）。
- 配音回退：flova 失败换账号，再回退本地 F5（不走 IndexTTS 主用路线）。

入口（固定，不要自造等价命令）：

```
scripts\new-knowledge-episode.cmd --slug <pinyin> --topic <选题> [--title 片名] [--city 成都]
scripts\make-knowledge-video.cmd <ep> [all|voice|heygen-plan|matte|compose|render] [--check] [--draft] [--force]
```

每期先 `--check` 干跑（不执行、不花钱），确认每步要做什么。`做视频 <期名>` 由 Agent 按本 runbook 执行，
从 episode.yaml 里第一个 `status` 不是 `done` 的阶段继续。

## Hard rules（违反就停下来问用户）

1. **不花真钱**：Agent 本地步骤只有 compose / render / 检查。flova 配音消耗积分、HeyGen 生成消耗额度，
   都属于「用户当次明确推进」才执行；`--check` 永不触发它们。
2. 只用用户自己的 HeyGen 数字人（Cool Breeze）和克隆/授权声音；不改原始录音；不动 `voices/clone/` 参考音。
3. 事实必须可回查：口播和画面里的数字、政策、平台数据，全部要能在 `<ep>/script/research.md` 里查到来源
   （链接 + 发布日期）。查不到的不要写进稿。不编造、不夸大。
4. 文字禁令：口播/字幕/画面**永远不用 `——` 或 `--`**（会被 TTS 读出来），用 `，` 或 `……`；
   **不用「最」「第一」「唯一」**等绝对化用语（episode loader 会拦）。打印给用户的消息里也不要出现 `——`。
5. 合规继承 `rules/compliance/common.md`：不承诺升值/学区/落户，不写「X 分钟到」，不出现电话/微信/二维码/网址。
6. 没有房源编号：knowledge 期是选题，不出现 listing id、不进目录名/画面/口播。
7. **画面永不出现内部文件名 / 路径 / 源文件标签**（如 `research.md`、`broll/…`、`S01`、`.json`）：观众可见的文字只能是面向观众的内容；数据溯源写在仓库文件里，不写上屏。
7. 不动 `.mcp.json` / `.grok/`；不 commit / push（除非用户明确要求）；密钥不进对话。

## Shared resources（全系列共用，不复制进本期）

- `assets/presenter/cool-breeze/presenter.yaml` — 主持人 profile（声音、HeyGen、matting、social 账号）。
  episode.yaml 的 `presenter: cool-breeze` 引用它；单期微调用 `presenter_override`，不改 profile 本身。
- `voices/clone/` — 克隆参考音（私有）。
- `templates/map-hub/shared/public/{fonts,brands,social}` — 字体与品牌 logo，stage 时链接进本期。
- 共享 Python 模块（只 import，不复制）：`pipeline/maphub/voice_config.py`（read_yaml）、
  `pipeline/maphub/voice_timing.py`（fingerprint / read_alignment / caption_frames）、
  `pipeline/maphub/sync_assets.py`（probe / img_size）、`pipeline/maphub/workspace.py`（series-aware staging）、
  `pipeline/maphub/heygen_plan.py`、`scripts/voice/clone_tts.py`（flova_minimax / indextts25 / f5 统一入口）。

## 0. New episode（Agent 执行，用户只给选题）

用户说「做视频」并给一个**知识类选题**时，Agent 建集（不让用户跑命令、不让用户选目录名）：

1. 序号 = `projects/knowledge/ep*` 最大值 + 1（本系列独立编号，从 ep01 起；map-hub 的编号互不影响）。
2. `scripts\new-knowledge-episode.cmd --slug <选题拼音> --topic <选题> [--title 片名] [--city 成都]`。
   默认城市**成都**；目录 `epNN-<slug>`；选题/片名/城市只进 episode.yaml 和 data/topic.json。
3. 建好的目录：`script/`（research.md + 人读稿）、`broll/{flova,muse,screens}/`、`voice/`、`heygen/`、
   `matte/`、`out/`、`data/`、`consent/`、`footage/heygen/`。episode.yaml 带三段占位 segments（oncam/voiceover）。

## 1. Script（episode.yaml segments + script/research.md）

脚本是 episode.yaml 里的 `segments:` 列表（loader: `pipeline/knowledge/episode.py`，写稿即改它）：

- **篇幅**：全片 80–90s（loader 在 70–100s 外提醒）；**露脸段合计 ≤ 55s**（`oncam_budget_s`，
  HeyGen 免费版一条 60s 上限，留 5s 余量；超出直接拒绝）。est_s 不写时按 4.6 字/秒估。
- **段型**：`oncam` = 露脸（HeyGen 数字人全屏）；`voiceover` = 画外音 + b-roll，必须带 `broll:` 或 `process:`。
  每段 `id`（S01…）、`text`（口播原文，TTS 逐字读）、可选 `cards:`（≤2 张数据卡 value/sub）、
  `process:`（流程动画步骤，如 ACN 录入→实勘→带看→签约）、`end: true`（结尾段，收进 END 品牌墙）。
- **事实**：每条数字/政策/平台数据在 `script/research.md` 有一行来源（链接 + 日期）。字卡的 value/sub 同样要能回查。
- **文字**：不用 `——`/`--`，不用「最/第一/唯一」；数字写法照顾口播（「五十二万」比「52万」读起来稳）。
- 结构建议：开场钩子（oncam）→ 正文（voiceover，2–4 段）→ 补充/团队（oncam）→ 总结+关注引导（oncam，end:true）。
  人读稿存 `script/script_vN.md`（episode.yaml `script_md` 指向当前版）。

## 2. Voice（flova MiniMax Speech 2.8 HD，passage 模式）

统一入口 `scripts/voice/clone_tts.py`（与 map-hub 共用），由 `make-knowledge-video <ep> voice` 调起：

1. `make_video.py` 先从 segments 写 `voice/narration.json`（engine + lines）。
2. engine 默认 `flova_minimax`（episode.yaml `voice_defaults`）：model `speech-2.8-hd`、voice `Gentle_Youth`、
   `mode: passage`（整篇一条过，保证语气连贯）、`tempo: 1.1`（atempo 1.1）。
3. passage 后自动跑：`passage_timings.py`（faster-whisper 词级时间戳）→ `retime_pauses.py`（停顿重排）→
   逐段切成 `voice/flova_minimax/<seg id>.wav` + 词时间戳 sidecar → 响度归一 **−16 LUFS**。
   缺 `av`（faster-whisper 依赖）时 timings 步会失败：先修环境再重跑，不要拿无时间戳的 wav 进正式片。
4. 消耗 flova 积分，**只在用户推进本期时跑**；失败（含积分）把错误原文告诉用户，不自动邀号。
5. 备选（显式选择）：Kaggle IndexTTS-2.5（`scripts/voice/push_indextts25.py`，克隆音，一张 T4）；
   最后手段本地 F5。Edge/估算字幕只用于 `--draft`。
6. 正式片要求 clone/正式配音 + 有效词时间戳；缺段或缺时间戳必须停（与 map-hub 同一标准）。

## 3. B-roll（broll/{flova,muse,screens}/，ref = episode.yaml 的 broll.ref）

优先级（**先生图兜底，再视频，App 界面只用真实截图**）：

1. **flova 生图兜底**（`broll/flova/<ref>.png`）：每条 voiceover 的每个画面先有 photoreal 关键帧兜底，
   保证任何时刻可出片。用 `gpt-image-2.5-sunburst`（成片级），prompt 写清是示意/装饰；
   **绝不**生成户型、室内实景、景观、小区/周边等事实性房源画面（知识片一般也不涉及）。
   生成后 `npm run assets:import` 登记 ai:true。
2. **Muse 视频**（`broll/muse/<ref>.mp4`）：街景、门店、城市氛围类镜头升级为 Muse 实拍感视频
   （Playwright 登录态，操作同 map-hub runbook §5）。有了 mp4 后把 episode.yaml 里该 ref 的 kind 从 flova 改成 muse。
3. **真实截图**（`broll/screens/<ref>.png|.mp4`）：**贝壳找房 App 界面、VR 看房、数据页一律用真实截图/录屏**，
   不用 AI 仿界面。截图里不能有电话/微信/他人隐私。
- 缺素材时 timeline 生成「pending 占位卡」，`--draft` 可渲染占位版；正式 render 的 preflight 会拦 pending。
- 时长：一个 voiceover 段内多条 b-roll 平分该段视觉时长（timeline.py 自动排）。

## 4. HeyGen（只露脸段；look 固定）

1. `make-knowledge-video <ep> heygen-plan`（内部先重建 timeline，再调共享 `pipeline/maphub/heygen_plan.py <ep> plan`）：
   把所有 oncam 段的正式配音拼成 `heygen/heygen_audio.wav` + `heygen/segments.json` + `heygen_segments.md`。
   露脸合计 > 55s 预算时此步直接失败，先压稿。
2. **人工/Playwright**（与 map-hub runbook §7 相同）：上传 heygen_audio.wav，选已保存 look
   **"Professional in suit on sofa"**（按名字选，找不到就停，不新建 look），生成**一条** 16:9 视频，
   每期只生成一次，下载到 `heygen/export.mp4`。
3. 去水印 7b：`pipeline/maphub/heygen_43.py`（同 map-hub），然后 `heygen_plan.py <ep> split` 按 segments.json
   切成 `footage/heygen/HG00.mp4`、`HG01.mp4`…（不覆盖 export.mp4）。
4. HeyGen 只用于 oncam 段；voiceover 段全程 b-roll，不出数字人。

## 5. Matting（片头标题分层用）

`make-knowledge-video <ep> matte`：对**第一个露脸段** `footage/heygen/HG00.mp4` 跑
`scripts\matting\matte_local.cmd`（默认 MatAnyone2，失败自动回退 RVM；Kaggle 为后备），
产物 `matte/HG00_alpha.webm` 复制为 `footage/heygen/HG00_alpha.webm`。
有 alpha 时片头标题在主持人**身后**；没有就压在暗角上（ KnowledgeKoubo 自动判断）。max_size 等参数来自 presenter profile。

## 6. Compose（时间线，纯本地）

`make-knowledge-video <ep> compose`（= `pipeline/knowledge/timeline.py <ep>`）：

- 读 episode.yaml segments + `voice/<engine>/<seg>.wav`（ffprobe 实际时长 + 词时间戳 sidecar）+
  b-roll 媒体 + `footage/heygen/` 切片，写 `data/timeline.json`（行 = 段，f0/f1 音频帧、v0/v1 视觉帧、字幕帧）、
  `data/footage.json`（b-roll/HeyGen 探测；缺媒体 → pending 卡）、`data/{episode,brands,social}.json`、
  `script_timed.md`（人读带时间稿），并把媒体复制进 `public/`。
- 无 wav 时 `--draft`：用 est_s + 估算字幕。wav 存在但词时间戳读不出：正式模式报错，draft 降级估算。
- 改稿/改配音/改 b-roll 后重跑本步（幂等）。

## 7. Render（KnowledgeKoubo，1440×1080 @30fps）

`make-knowledge-video <ep> render [--draft] [--still N] [--concurrency 4]`：

1. preflight：data 五件套齐全；正式片要求 audio_mode=clone（真实配音）、oncam 段有 HeyGen 素材、无 pending b-roll。
2. stage：`pipeline/maphub/workspace.py` 按 episode.yaml `series: knowledge` 选 `templates/knowledge/remotion`，
   复制到 `<ep>/work/remotion`，链接 node_modules、`src/episode`→`data/`、`public/`（含共享 fonts/brands/social）。
3. `npx remotion render src/index.ts KnowledgeKoubo out\<draft|final>_KnowledgeKoubo.mp4 --gl=angle`（cwd = work/remotion）。
4. 合成内容：露脸段 HeyGen 全屏（首段片头标题卡；end 段讲完叠 END 品牌墙）；画外音段 b-roll 平分 +
   数据卡（左列）+ 流程动画（process）；口播字幕条（品牌带上方居中）；底部 BrandStrip；
   右上角 SocialBadge（**视频号 @贝壳-TV / 抖音 @贝壳TV**，来自 presenter profile social）。
5. 渲染后照 map-hub runbook §10 做 QA：响度 −16 LUFS、抽 ≥4 个不同镜头静帧人工过目
   （`--still N`）、字幕/水印/品牌带无碰撞、pending 卡不出现在正式片。

## 排障速查

- `est_s 超出合理范围` / `露脸段合计超过 oncam_budget_s`：压稿或减段，别放宽预算。
- `缺 footage/heygen/HG00.mp4`：先走 §4 的 HeyGen + 7b + split。
- `缺 av 模块`（passage_timings）：faster-whisper 依赖没装全，修环境后重跑 voice。
- `不是 knowledge series`：episode.yaml `series:` 被改回 map-hub，或把房源期拿进了本流水线；房源期走 `scripts\make-video.cmd`。
- render preflight 报 pending：补 broll/ 媒体后重跑 compose，或 `--draft` 出占位版。


## 品牌 logo 库（2026-10-14 登记，后续各期复用）
- Remotion 片中品牌条：`templates/map-hub/shared/public/brands/`（单色 `*_mono.*`，原图在 `original/`，来源见 `brands.md`）。
- 海报/静帧用（含彩色 21世纪 `c21.png`、`ke.png`）：`assets/brands/logos/`。
- `templates/knowledge/brands.json` 的 `logoLibrary` 字段列出了每个品牌对应的文件。
- 已有：贝壳、链家、德佑、富房（含“不动产”框）、21世纪不动产、中环地产、住商。中环来自用户提供的带水印图，正式发布前最好换成官方文件。
- 海报生成示例：`projects/knowledge/ep01-intro/broll/canva/make_posters.py`（品牌墙 C、规模卡 B 的 logo 条）。

---

## ep01-intro v5 实际流程（2026-10-16 定稿，16:9 1920x1080，后续知识期照此执行）

> 本节记录 ep01-intro v5f 实际跑通的做法。与上文 4:3/1440x1080 旧流程冲突时，**以本节为准**。
> 工作目录：`projects/knowledge/ep01-intro/jobs/v5_stills`（Remotion 工程，`public` 为指向 `ep01-intro/public` 的 junction）。

### A. 稿件规则
- 只写可回查的事实，来源写进 `script/research.md`（链接 + 日期）。ep01 用到的数字：链家/贝壳 52.3 万经纪人、6.1 万门店（HKEX 2025 年度业绩）；德佑成都 1000+ 门店（新华网）。查不到就不写。
- 不用「最」「第一」「唯一」等绝对化用语；口播/字幕不出现 `——` / `--`（TTS 会读出），用 `，`。
- 数字在 TTS 文本里写成汉字读法（例：`21世纪` → 字幕匹配时归一为 `二十一世纪`）。
- 自我介绍固定句：**「我是小ONE，你的房产顾问」**；结尾固定句以「我是小ONE」开头（HeyGen 结尾段从这里切）。
- 上屏字幕：去掉全部标点符号（regex `[^\p{L}\p{N}\s]`），深色半透明胶囊 `rgba(0,0,0,0.55)` + 白字。

### B. 配音（VO）
- flova MiniMax TTS（`scripts/flova/flova_minimax_tts.py`），音色 **Gentle_Youth**，`tempo: 1.1`，`mode: passage`（整稿一次调用，按行切出 `S01..S07.wav` + 逐字时间 `Sxx.json`）。
- 响度统一 **-16 LUFS**。
- 逐字时间（whisper / TTS 返回的 words）→ 重排 `src/episode/timeline.json`：每段 `v0/v1`（画面）与 `f0/f1`（音频，比画面晚 6 帧 = 0.2s 引入），字幕 `caps` 按字对齐。
- 片尾：`total` 比最后一句多留 30 帧（1s 定格），`lines[-1].v1 = total`。
- 积分账号按余额轮换（kid3/5/6/7），失败换号，不要重复跑同一句。

### C. 露脸分配（HeyGen 预算）
- HeyGen 免费档单条 **< 60s**（runbook 预算 ≤55s）。ep01 露脸：S01（开场自我介绍）、S02（判断标准）、S06（房东委托）、END（「我是小ONE……」到结尾）。其余段（S03/S04/S05、S07 前半）用图文/动效，不露脸。
- 露脸段全屏：原始 16:9 HeyGen 画面铺满 + 抠像人物置顶，图形放在人物身后（Room 组件：plate → 图形 → alpha 人物）。不再用 PiP（`SHOW_PIP=false`）。

### D. HeyGen 一次生成（ONE pass）
1. 从 v5 VO 导出段落：`hg_S01/S02/S06`（整段 wav）+ `hg_END`（S07 从「我是小ONE」前 0.05s 到结尾），各段首尾补 0.2s 静音。
2. 拼成 **一条** `hg_ALL.wav/.mp3`：顺序 S01,S02,S06,END，段间 0.6s 静音，首尾 0.2s；记下每段在 hg_ALL 内的起止（ep01：0.200–11.840 / 12.440–26.730 / 27.330–42.670 / 43.270–49.552，总 49.75s）。
3. HeyGen 网页：avatar **Cool Breeze**，已保存 look **"Professional in suit on sofa"**（按名字选，找不到就停），16:9，免费 720p，脚本来源 = **上传音频** hg_ALL（不用 HeyGen 声音/打字）。只生成一次，下载为 `ep01-intro/heygen/export.mp4`（1280x720, 25fps）。
4. 用音频互相关核对 export 与 hg_ALL 的头部偏移（ep01：+0.023s，恒定）。

### E. 去水印（右下角 HeyGen 标）
- `python pipeline/maphub/heygen_mark.py <ep>`（只读 export.mp4，写 `export_nomark.mp4`）。
- 需要 `heygen/mark/repair.png`：同一 look/同一房间时，**直接复用已去水印的干净帧**（ep01 用 ep07 `export_nomark.mp4` 第 2.3s 帧，背景差 ~2/255），不必再调 flova；不同 look 才按脚本提示走 flova generate_image。
- 检查右下角裁切图无残影。

### F. 抠像
- `python scripts/matting/matte_local.py heygen/export_nomark.mp4 --out heygen/dewm`（MatAnyone2，失败自动回退 RVM）→ `export_nomark_alpha.webm`。整条 export 一次抠，切段时与 RGB 同步切。

### G. 切段（`heygen/cut_v5.py`）
- 每段 RGB 与 alpha 同参数切：`ss = hg_ALL段起点 - 0.2 + 头部偏移 + SYNC[段]`（新集 SYNC 全部为 0），`fps=30, scale=1920:1080:flags=lanczos`，帧数 = 该段 `v1-v0`；export 不够长时 `tpad clone` 补尾，`ss<0` 时 `tpad` 补头。输出 `public/footage/heygen169/HG_S01|HG_S02|HG_S06|HG_END(.mp4/_alpha.webm)`。
- **口型**：不做口型补偿（默认，2026-10-19 决定）：之前看到的不同步来自远程桌面播放；只有用户明确要求时才做 SyncNet 检查/平移。
  - 历史：ep01 `cut_v5.py` 的 SYNC 表（`HG_S01 -0.12, HG_S02 -0.10, HG_S06 -0.12, HG_END -0.12`）只适用于 ep01，不作为新集默认值。
  - 若用户要求检查：SyncNet（box `syncnet_python`）AV offset 为负 = 嘴型早于声音；mediapipe 开合法有 +5 帧偏置，不可用。
- 时间线：`timeline.json` 中 `clip` 填 `HG_S01/HG_S02/HG_S06`；END 在 S07 内以 `cta = (f0-v0) + round((5.0-0.2)*30)` 起播 `HG_END`。片段音轨静音，只用 VO。

### H. 版式与画面
- 16:9 1920x1080，浅色系，无青/蓝主色；标题字体 Alimama ShuHeiTi；动效只用 video-shotcraft 库。
- 卡片：实色/磨砂卡（卡内 backdrop blur + 较高不透明度、1.5px 亮边、柔和投影），**背景不模糊**。
- **开场 Intro C**（默认 `introAlt="C"`）：不挡脸/胸口的非对称名片。
- **S05 电影化**：每个要点轮流占满画面，全幅 Muse 照片 + 慢速 Ken Burns + 左下实色白卡（大号序号 + 标题 + 短副文案），条目间转场各不相同（crane-rise-reveal / circle-match-iris / color-block-step-wipe / bottom-push-stack-wipe），最后 deck-deal 4 个小 chip 收束；最后一条单独停留 ≥2.5s。每张图按主体位置设 `POS`（卡片位置）与 `ORIG`（Ken Burns 焦点），卡片 `zoom:0.85`，**卡片避开人脸/手/关键物**。
- **照片优先**：能用照片表达的不用图标；AI 生成图加小号「示意图」标签。图片要像专业摄影 + 专业修图，无水印、无错字、无可读的假政策文字/机构名/文号。
- 右上角平台角标（无底色，`right:44, top:34` 安全边距）+ 底部品牌条保留；画面不出现文件名。

### I. Muse / flova 生图
- 先网搜真实参考（例：贝壳签约服务中心实景），记录参考 URL，再生成；不画错真实 logo，仍标「示意图」。
- Muse 在 box 浏览器里操作（Playwright 会话）；统一暖色、自然光、真实摄影质感，人物为**中国人面孔**；输出 2048x1152 放到 `public/broll/v5/`。
- flova `gpt-image-2.5-flare`（original:true）用于其余配图；被内容过滤时软化措辞（如「政府公文」→「正式打印通知」）。

### J. 片尾
- 保留原版：贝壳 app 图标（矢量重绘，#3072F3 圆角方块 + 白色屋顶/微笑，带蓝色柔和投影）+「我是小ONE 欢迎关注」，「小ONE」下手绘琥珀色下划线（shotcraft marker-underline 描边动画）+ 琥珀副标题 + 平台关注胶囊 + 5 个品牌 logo 卡；定格 1s。

### K. 渲染（两个平台各出一版）
在 `jobs\v5_stills` 下：
```
npx remotion render src/index.ts KnowledgeKoubo ..\..\out\drafts\v5\ep01-intro_test_v5f_douyin.mp4 --gl=angle --props=douyin.json --codec=h264 --crf=20   # 测试
npx remotion render src/index.ts KnowledgeKoubo ..\..\out\release\ep01-intro_douyin.mp4 --gl=angle --props=douyin.json --codec=h264 --crf=20             # 定稿
npx remotion render src/index.ts KnowledgeKoubo ..\..\out\release\ep01-intro_shipinhao.mp4 --gl=angle --props=shipinhao.json --codec=h264 --crf=20       # 定稿
```
- `douyin.json` = `{"platform":"douyin"}`，`shipinhao.json` = `{"platform":"shipinhao"}`；platform 同时切换右上角标与片尾胶囊（抖音 @贝壳TV / 视频号 @贝壳-TV，来源 `src/episode/social.json`）。
- 单帧检查：`npx remotion still src/index.ts KnowledgeKoubo out_keys\x.png --frame=N --gl=angle --props=douyin.json`。
- 验收：ffprobe（1920x1080, 30fps, h264+aac）；抽帧看角标/片尾胶囊/无水印/无占位标签。
- 放大与超分：见 `CONVENTIONS-shared.md` §7（默认 lanczos 720p→1080p，超分仅在用户明确要求时做）。

### 输出目录约定
见 `CONVENTIONS-shared.md` §1。知识类命令：`pipeline/knowledge/make_video.py --step render [--platform douyin|shipinhao]` 直接写 `out/release/<episode>_<platform>.mp4`；Remotion 工程里手动渲染时测试输出到 `..\..\out\drafts\<ver>\`，定稿输出到 `..\..\out\release\`。

## 可复用到房源类（map-hub）的做法
共用部分已收进 `CONVENTIONS-shared.md`；房源类仍需各自确认的迁移项见 `docs/NOTES-knowledge-to-listing.md`。要点：HeyGen 一次生成 + hg_ALL 拼接与段表、复用干净帧去水印、整条抠像后同步切段、默认不做口型补偿、16:9 原始 plate + 抠像置顶的 Room 分层、字幕胶囊与去标点、照片优先 +「示意图」、Muse 先找参考再生成、卡片避脸、平台 props 双版本渲染、片尾 1s 定格。

## 封面（系列统一模板，3:4 + 4:3）
- 模板：`jobs/v5_stills/src/Cover.tsx`（组件 `KnowledgeCover`），在 `Root.tsx` 注册 `KnowledgeCover3x4`（1080x1440）与 `KnowledgeCover4x3`（1440x1080）。
- 版式：底图全幅 + 象牙色渐变（3:4 顶部 / 4:3 左侧）；左上贝壳矢量图标 +「贝壳」；琥珀色期号胶囊「01 小ONE讲房产」；阿里妈妈数黑体大标题（两行），`hl` 子串下手绘琥珀下划线（与片尾一致）；可选琥珀副标题。不放平台账号。
- 安全区：3:4 文字在居中 1:1 方块内（y 180–1260）并留 8% 边距；4:3 文字在左侧 54%、7% 边距；人物头部不压字（3:4 底图默认下移 `bgShift=0.17`）。
- **推荐默认流程（2026-10-21 用户确认）**：复用系列模板 `Cover.tsx` + 已有主持人底图（`public/cover/ep01_bg_3x4.png / _4x3.png`），只改文字（期号 `ep`、标题 `lines`/`hl`、房源副标题 `sub`）。新 flova 底图（`gen_bg.py`，约 24 积分）为可选项，仅在用户要求时生成。
- Windows 编码坑：在 PowerShell 里用 here-string 管道给 `python -` 生成 props JSON 时，中文会被替换成一串问号（控制台代码页非 UTF-8），封面标题直接渲染成问号。做法：props JSON 在 box 上（或用 UTF-8 编辑器）写好，以 UTF-8 保存后再拷到 PC（CopyFromBox），渲染前用 `python -c "...encode('unicode_escape')"` 确认是 `\u6210...` 而非问号；渲染后放大看一眼标题区。
- 底图生成（可选，仅用户要求时；2 张约 24 积分）：`python cover/gen_bg.py <profile> bg_3x4,bg_4x3`（flova gpt-image-2.5-flare，original:true，count 1，2K；参考图 `cover/ref/look_frame.png`（export_nomark 帧）+ `look_src.png`，同一人物、暖色象牙/琥珀、无蓝青、无文字）。count 2 + 参考图的预估会超过单账号余额，用 count 1。挑选后复制到 `public/cover/epNN_bg_3x4.png / _4x3.png`。
- 渲染（在 `jobs\v5_stills`）：
```
npx remotion still src/index.ts KnowledgeCover3x4 ..\..\out\release\cover_3x4.png --props="{\"bg\":\"cover/ep02_bg_3x4.png\",\"lines\":[\"标题第一行\",\"第二行\"],\"hl\":\"关键词\",\"ep\":\"02\"}"
npx remotion still src/index.ts KnowledgeCover4x3 ..\..\out\release\cover_4x3.png --props="{\"bg\":\"cover/ep02_bg_4x3.png\",\"lines\":[\"标题第一行\",\"第二行\"],\"hl\":\"关键词\",\"ep\":\"02\"}"
```
  props：`bg, lines[], hl?, series?(默认 小ONE讲房产), ep?, sub?, brand?(默认 贝壳), bgPos?, bgShift?`（也可写成 json 文件用 `--props=cover_ep02.json`）。标题每行 ≤6 字为宜。

