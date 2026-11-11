# CONVENTIONS — 知识类与房源类共用规范

> 现行生产交接见 `PRODUCTION.md`；旧 project 生产入口已移除，测试工程不得作为新建模板。

> 适用：`projects/knowledge/*`（知识类，`RUNBOOK-knowledge-koubo.md`）、`projects/listing/*`（房源类，`RUNBOOK-map-hub-koubo.md`）、`projects/interview/*`（小ONE会客厅，`RUNBOOK-interview.md`）。
> 三类内容独立编排、共用基础能力；发布编号统一，由 `npm run episodes` 计算，目录与入口见 `architecture.md`。旧 `projects/map-hub` 路径已移除（2026-10-30）。各类型独有的规则写在各自 runbook。会客厅对第 2、3、6a、字幕各节的覆盖写在本文末节。
> 冲突时：本文件 > 主题文档（tts / voice-clone / matting / kaggle-gpu）；类型独有规则只在本类型内覆盖本文件。会客厅末节只覆盖会客厅。

## 0. 项目用途与素材许可

按用户于 2026-10-31 的明确要求，**本项目仅用于非商业用途**。房源类、知识类和小ONE会客厅的素材选型、第三方代码与服务接入均按非商业用途处理；允许使用符合其非商业条款的素材或代码（包括 CC BY-NC 等许可），不要求额外取得商用授权，不得仅因不允许商用或缺少商用授权而排除候选或阻断制作。署名、修改、再分发、来源记录、API 使用条件和服务费用仍按各自条款执行。

- 适用范围：房源类、知识类、小ONE会客厅全部期数，以及共用工具、动效、音效库和背景音乐。
- 优先选免费且允许本项目非商业使用的资源；允许 CC0、CC BY、CC BY-SA、CC BY-NC 等许可，但使用、修改与分发分别满足对应条件。
- 非商业使用无需额外商用授权；不要仅因素材不能商用而要求换源、购买商用授权或暂停制作。音效库/API 同样按其非商业使用条款评估接入。
- 音效、音乐、字体、图片、视频及第三方代码仍记录来源与许可；应署名的在规定位置署名。免费预览、缓存文件或可下载状态本身不替代使用许可。

## 1. 输出目录与命名
- **`<EP>/out/release/`** 只放最终交付：`<episode>_<platform>.mp4`（如 `ep01-intro_douyin.mp4`）、`cover_3x4.png`、`cover_4x3.png`、`publish.md`。理由：交付物一眼可见，不会和测试片混淆。
- **`<EP>/out/drafts/<ver>/`** 放测试片、关键帧、对比片段。理由：迭代产物可追溯，不污染交付目录。
- **`<EP>/out/archive/`** 放被替代的旧成片，文件名带日期/时长说明。理由：可回看，不误发。
- 中间产物（`heygen/`、`matte/`、`footage/`、`voice/`、`work/`、`jobs/`）留在原处，不进 `out/`。理由：便于重跑和清理。
- 每个平台各导出一版，用 Remotion `platform` prop（`douyin` / `shipinhao`）切换角标和关注信息。理由：同一工程，零手工改字。

## 1a. 审片阶段（只有两档）
- **粗剪 / roughcut**：画面、配音、字幕、动效、角标、品牌条全部齐；超分可选（默认跳过），混音可以粗糙。存 `out\drafts\roughcut_v<N>\<episode>_roughcut_v<N>.mp4`，同目录 `notes.md` 列出占位素材、假设和未决问题。用户审片后迭代 v1、v2……
- **成片 / final**：用户确认粗剪后，按平台导出到 `out\release\<episode>_<platform>.mp4`。
- 不做 animatic、精剪等其他中间档。理由：用户只审这两档。

## 2. 配音
- 默认 flova MiniMax Speech 2.8 HD，音色 **Gentle_Youth**，**整段一次调用**（passage 模式，约 10 积分），`atempo 1.1`（保持音高），响度 **−16 LUFS**。理由：韵律最自然，成本最低，全系列音色一致。
- 稿件里不出现 `——` / `--`（TTS 会念出来），用 `，` 或 `……`。理由：实测会被读成「减减」。
- 逐字时间必须来自**最终用于合成的 wav**（Whisper/返回的 words 对齐）；处理后重新对齐。理由：字幕不漂。
- flova 失败时按各类型 runbook 的回退顺序，**不出无声版**。

## 3. 数字人（HeyGen）
- 只用用户本人的 avatar **Cool Breeze** + 已保存 look **"Professional in suit on sofa"**（按名字选，找不到就停）；音频一律**上传我们的配音**，不用 HeyGen 声音或打字。理由：授权和形象一致。
- **每期只生成一次**，16:9、免费 720p，露脸音频 **≤55s（硬上限 60s）**；把所有露脸段拼成一条上传。理由：免费额度一期一条。
- 生成后用音频互相关核对头部偏移；**口型**：不做口型补偿（默认，2026-10-19 决定）：之前看到的不同步来自远程桌面播放；只有用户明确要求时才做 SyncNet 检查/平移。切段 SYNC 默认 0（知识类、房源类都一样）；`heygen_plan.py split --sync` / episode.yaml `heygen_sync` 保留为可选项，默认关闭。ep01 `cut_v5.py` 里的 SYNC 表是历史记录，只适用于 ep01。
- 去右下角水印、抠像（MatAnyone2，失败自动回退 RVM；Kaggle 为后备）在**切段之前**对整条 export 做。理由：RGB 与 alpha 同参数切，逐段一致。
- 分层：原视频背景 → 文字/图片 → 抠出的人 → 字幕胶囊 → 品牌条。图形不压脸、手、胸口。

## 4. 字幕与角标
- 上屏字幕去掉全部标点（`[^\p{L}\p{N}\s]`），居中深色半透明胶囊 `rgba(0,0,0,0.55)` + 白字，位于品牌条上方。理由：干净、手机上易读。
- 右上角只放一个平台角标（图标 + 账号，无底色，留安全边距）；抖音 @贝壳TV / 视频号 @贝壳-TV（`social.json`）。
- 画面不出现内部文件名、路径、段落 id。
- 底部品牌条保留：链家、德佑、富房、CENTURY 21、中环，任何地方不裁切（两类通用；旧流程「拦截贝壳/链家等平台名称或 logo」的规则已作废，品牌条除外的其他平台引流信息仍不出现）。

## 5. 视觉
- 浅色暖调（象牙 / 暖白 / 琥珀强调），**不用青/蓝主色**；标题字体阿里妈妈数黑体。理由：系列识别度。（房源类同样适用；旧 `one-sentence-workflow.md` 的荧光绿强调色和硬切已作废。）
- 卡片用实色/磨砂卡（1.5px 亮边 + 柔和投影），**背景不做模糊**。
- 动效只用 video-shotcraft 库；入场缓动不过冲，同时入场元素 ≤5 个。
- **照片优先**：能用照片表达的不用图标；AI 生成图标「示意图」。

## 6. 素材生成
- 生图：flova GPT Image 2.5（Flare 日常 / Sunburst 精修），`original:true`；不画错真实 logo，不出可读的假政策文字、机构名、文号。
- Muse：在浏览器会话中操作，先找真实参考（记录 URL），统一暖色真实摄影风格，人物为中国人面孔。
- 积分：按余额轮换账号；带参考图时一次只生成 1 张；同一张不重复跑；只清理 0 余额账号。

## 6a. 每期独立素材目录
- 每期都有自己的素材目录，不跨期共用，不放进 `templates/`。理由：便于复用、交接和清理。
- `<EP>\footage\raw\`：原始素材（视频、`photos\`），只读，永不修改、移动或删除。
- `<EP>\footage\assets\`：本期素材，只放**已采用**的成品（新房用 `brochure\`、`renderings\`、`sandtable\`、`map\`，开发商原件放 `<EP>\sources\docs\`；完整目录见 docs/FOOTAGE-SPEC.md）。租赁/二手房：
  - `floorplan\`：CRM 户型图原图 `floorplan_crm_original.*`、清理版 `floorplan_clean.png`（含文字）/ `floorplan_clean_notext.png`、透明抠图 `floorplan_cutout*.png`、`README.md`（来源、核对结果）。
  - `photos\`：采用的 Muse 增强图 `<room>_muse.png` + `sources.md`（原图、Muse 线程、日期、备注）。
  - `map\`：采用的地图底图和 POI 图片。
  - `README.md`：本目录索引。
- 试验和中间结果留在 `<EP>\out\drafts\`，采用后才复制进 `footage\assets\`。
- 公共素材（主持人、品牌、角标、字体）放公共区（`assets/`、`templates/shared/public/`），不按期复制。
- 新建一期时 `scripts\new_episode.cmd` 按类别建好以上目录和 README；其他目录由工具第一次写入时创建。

## 7. GPU / Kaggle
- 一律用 `C:\ProgramData\miniconda3\python.exe` 跑 Kaggle 脚本；**不在队列里等**：推送后约 45s 仍是 QUEUED 就删除会话并重推，最多 10 次。理由：用户的队列策略。
- **超分是可选步骤**：默认 lanczos 720p→1080p；只有用户明确要求才走 Kaggle 超分（SeedVR2）；10 次仍失败就跳过超分，保留 lanczos 版本**照常交付**，在报告里注明（两类通用；`push_job.py --kind sr` 此时退出码 23，不是流水线失败）。配音失败回退本地 F5 不变；其他 Kaggle 任务失败仍停下上报。
- 每期 Kaggle 产物各自独立，不跨期引用。

## 8. 质检（交付前全部通过）
- `ebur128` 响度 −16 ±0.5 LUFS；`freezedetect` 无冻结；`ffprobe` 分辨率/帧率/音轨正确。
- 联系表（`fps=1/6,tile=6x4`）+ 关键静帧：角标、字幕、品牌条、片尾无遮挡、无水印、无「占位」标签。
- 报告：路径、时长、露脸秒数、LUFS、联系表、已知问题。

## 9. 封面
- 统一模板：3:4（1080x1440）+ 4:3（1440x1080）。flova 生成底图（主持人参考 HeyGen look，暖色），文字由代码合成：阿里妈妈数黑体大标题、关键词琥珀手绘下划线、期号胶囊、贝壳矢量图标，不放平台账号。
- 安全区：3:4 文字在居中 1:1 方块内；4:3 文字在一侧 54% 内；人物头部不压字。
- 模板实现见知识类 `jobs/v5_stills/src/Cover.tsx`；房源类可复用同一组件（`series` / `lines` / `hl` props 改文案）。
- **推荐默认流程（2026-10-21 用户确认）**：复用系列模板 `Cover.tsx` + 已有主持人底图（`public/cover/ep01_bg_3x4.png / _4x3.png`），只改文字（期号 `ep`、标题 `lines`/`hl`、房源副标题 `sub`）。新 flova 底图（`gen_bg.py`，约 24 积分）为可选项，仅在用户要求时生成。
- Windows 编码坑：在 PowerShell 里用 here-string 管道给 `python -` 生成 props JSON 时，中文会被替换成一串问号（控制台代码页非 UTF-8），封面标题直接渲染成问号。做法：props JSON 在 box 上（或用 UTF-8 编辑器）写好，以 UTF-8 保存后再拷到 PC（CopyFromBox），渲染前用 `python -c "...encode('unicode_escape')"` 确认是 `\u6210...` 而非问号；渲染后放大看一眼标题区。

## 10. 内容合规
- 只写可回查的事实（来源链接 + 日期，或房源数据 / map.py 结果）；查不到就不写。
- 不用「最」「第一」「唯一」等绝对化用语；不承诺升值、学区、落户；不写「步行 X 分钟」。
- 不出现电话、微信、二维码、网址；不出现内部 listing id。
- 只用用户本人的数字人和授权声音；原始录音只读。
- 不动 `.mcp.json` / `.grok/`；不 commit / push（除非用户明确要求）；密钥不进对话和文件。


## Professional real-estate terms (2026-10-20)
Narration, captions, box labels and cards use standard 房产 terms, not plain descriptions of what is visible: 干湿分离 (not 玻璃淋浴隔断), 南北通透, 飘窗, 精装/简装, 客厅开间, 通顶衣柜, 整体橱柜, 双卫, 明厨明卫, 一梯两户, 双线换乘, etc. Use a term only when the footage or CRM data supports it (no 南北通透 without a north–south layout; no 建面/套内 without the area basis). Plain wording stays only where no standard term exists. Still no 最/第一/唯一 and no ——.

## Map data sources and screenshot boundaries (2026-10-20)
- OpenStreetMap is used ONLY for area boundaries (polygons). Everything else (base map tiles, POIs, distances, walking routes, gates) comes from Amap via map.py. If anything on a map uses OSM for something else, switch it to Amap.
- If OSM has no polygon for a needed place (common for residential compounds) and Amap gives none, ask the user to upload a screenshot (e.g. the Amap app showing the boundary and gates). The agent redraws the boundary from it: georeference on at least two Amap POIs visible in the screenshot (e.g. the community pin plus a nearby POI; check that a known gate falls on the redrawn edge), save the screenshot under footage/assets/map/ and the polygon as GCJ-02 GeoJSON (footage/assets/map/<name>_boundary.geojson), then load it with `map.py aoi "<name>" --source manual --file <geojson>` and store it in pois.json `aoi` with the source noted. Gates and distances stay as measured unless the user asks to change them.

- **PiP position is fixed** (user rule 2026-10-20: 小窗口在不遮挡关键信息时不要挪动位置). Every presenter PiP (map lines and B-roll lines) uses ONE rect: bottom-right, right 50 / bottom 190, 330x248 (`PIP_R`). Move it only when that rect would cover key info (captions, rent, labels, tracked boxes, map route or markers), by the smallest shift that clears it, and record the line id + reason in `PIP_EXCEPT` (MapHubKoubo.tsx). Per-line `pipPos` is ignored. The END card's upper-right host window is a layout of its own (summary panel + brand rows), not a PiP move.

## Motion tempo (user rule 2026-10-20: 动效节奏一致，不要有的慢有的快)
- One consistent motion tempo across the film. Each segment keeps its own animation style, but every element uses the shared timing scale `TEMPO` in `src/lib.ts`: entrances 8-10 f (E_OUT or the hook spring), exits about 8 f, staggers 3-4 f, camera moves, route draws and 3D-scene flights 16 f (E_IO), scene transitions about 10 f.
- No element may run noticeably slower or faster than this. A new animation reuses `TEMPO` rather than hard-coded frame counts, and any exception is commented with its reason (e.g. a reveal held for a narration phrase).
- Exact values: entrance 10 f, exit 8 f, stagger 4 f, camera/route/3D flight 16 f, transition 10 f.
- The hook alone keeps spring bounce + squash-and-stretch, on the same 10 f settle; elements enter one at a time when the narration mentions them (never all at once). Bounce is not used outside the hook.


## 字幕规则 (Captions) - authoritative, 2026-10-21
- 逐字跟口播，一个分句一条，数字用阿拉伯数字（347米、3000、4号线）；不允许摘要式字幕。
- 时间：脚本原文与 faster-whisper（`pipeline/asr/align_voice.py`，small，中文）逐字时间戳模糊对齐，文字取脚本不取识别结果。
- 构建检查：字幕拼起来不等于完整口播时拒绝渲染（v8f）。
- 位置：居中，固定在距底 118px。只有会遮挡重要信息（租金、标签、路线、标记）时才挪，最小位移，记录帧段和原因（ep02：主帧 150-240 右对齐，避开价格行）。PiP 不得遮挡字幕。

## 租赁房源 ep02 补充 (2026-10-21)
- 开场：真实 CRM 周边房源 + 快速滑动（28 f）配音效，无「示意」标签，无左滑；`hub.json opener.filter` 为每期开关。
- 户型图无白边。
- 地图/交通/周边段落不得长时间静止；POI 配实地照片并记录来源与许可（CC BY-SA 署名写进发布简介）。数据来源见上文 Map data sources。
- 口播剪辑效果第一，不以缩短时长为目标。
- 音效 Mixkit 或自生成；BGM 可取自剪映缓存（见 RUNBOOK-map-hub-koubo.md「租赁房源剪辑规范补充」），本项目不作商用。
- 质检在 PC 上用数据核对，最多一张 contact sheet，不来回传帧。
- 详细规则与 changelog：RUNBOOK-map-hub-koubo.md 末尾。

## 小ONE会客厅（series: interview）覆盖

只作用于 `projects/interview/*`。房源和知识类仍按上文。

- 出镜是嘉宾本人，机位固定中近景。小ONE在镜头外提问，保留小ONE的现场声。不用 HeyGen、不用 TTS、不用声音克隆、不用默认变速，也不做口型生成。
- 配音来自现场分轨：主持声、嘉宾声、环境底噪。`atempo` 固定为 1。停顿和呼吸保留。开头和结尾都要核对偏移；置信度不足或尾部漂移超过 40ms 时交给人确认，不自动拉齐。
- 字幕来自校正后的口播，再按剪辑清单重映射到成片时间。采访提纲不是字幕。没有校正稿就保持待导入，不编造句子。`pipeline/asr/align_voice.py` 只对齐已有稿，会客厅不用它把提纲套成字幕。
- 首版画幅 16:9、1920×1080。帧率只允许 25 或 30。时间单位是整数毫秒，`source_in_ms` 含入点，`source_out_ms` 不含出点。25fps 与 30fps 的入场、出场按真实秒数换算，不把 30fps 的帧数直接拿去用。
- 原始机位和原始录音只读，目录名按角色存放，不套用房源的 `客厅_1` 这类房间文件名。抠像只处理已确认剪辑范围加手柄，不整段抠一场长采访。
- 画面上的数字必须带来源、采集日期和统计口径，并标明挂牌价、成交价、系统样本或经纪人观点。缺数值就写进核对清单「不推断」，不上数字卡。内部编号、客户联系方式和未授权信息不上屏。
- 品牌条和平台角标仍用公共组件。视频号 @贝壳-TV，抖音 @贝壳TV。会客厅自己的栏目标在左上，不显示「知识科普」。
- 没有参考帧时，虚拟会客厅只是可替换占位，不能写成已经匹配真实机位。技术测试渲染不是真人验收。


