# AGENTS.md — ReelEstate 所有编码 Agent 的总规则

> 适用于 Codex、Claude Code、OpenCode 及任何在本仓库工作的 Agent。`CLAUDE.md` 只引用本文件。
> 文档/规则用中文写，代码、标识符、文件夹名用英文（或拼音）。

## 1. 项目目的

为一位中国房产视频创作者（抖音 + 微信视频号）批量制作**科普/讲解风格**的房源视频：
真人口播（全屏 ↔ 左下/右下小窗 PiP 切换）+ Canva 设计的信息卡 + Remotion 动效 + 可选 AI 配音（qwentts.cpp）。

- 默认导出：**4:3 横版 1440×1080 @30fps**；可选竖版 **3:4 1080×1440**、**9:16 1080×1920**。
- 三个分类：`rental`（租赁）、`resale`（二手房）、`new-home`（新房）。
- 合规是硬约束：视频号《房地产行业公约》（2026-05-12 生效）、《广告法》、《房地产广告发布规定》、《住房租赁条例》等。见 `rules/`。

## 2. 目录结构

```
AGENTS.md / CLAUDE.md / README.md
package.json          # 固定命令入口（npm scripts）
.env.example          # TTS 路径模板；真实 .env 不提交
rules/                # 所有规则（Agent 必读）
  compliance/         # common.md + rental.md / resale.md / new-home.md
  style.md            # 视觉与讲解风格
  workflow.md         # 标准流程
  reference/          # 原始调研文档（带来源链接）
remotion/             # Remotion 4 + TypeScript 渲染工程
  src/Root.tsx        # 注册 Rental/Resale/NewHome × 4x3/3x4/9x16
  src/shared/         # PresenterFrame, Captions, InfoBar, DisclaimerBadge ...
  src/compositions/   # rental/ resale/ new-home/
pipeline/             # Python（尽量只用标准库）
  new_project.py      # 新建项目
  tts/qwen_tts.py     # 分段 TTS
  check/check.py      # 合规检查（render 前强制）
  render.py           # 检查 + 渲染
  preview.py          # Remotion Studio 预览某项目
  schema/             # JSON Schema（common + 各分类）
  make.py             # 一句话成片总入口（固定阶段，见 §3A）
  stages/             # brief / listing / wall / map_fetch / assets / script_stage
  tts/edge_tts_stage.py  # edge-tts 草稿配音 / 自录口播校验
remotion/src/styles/  # 风格预设 tokens：mediastorm.ts + fonts.ts（固定影视飓风）
remotion/src/shots/   # 共用镜头组件：ListingWall RoomCard FloorplanLocator LocationLabel SpecCard DataNumber MapReveal ShotVideo
remotion/src/assets/fonts/  # 可商用字体 + 许可证（README.md）
rules/style/mediastorm.md   # 影视飓风风格测量规则（写脚本/分镜前必读）
rules/effects/              # 动效目录 catalog.json + README（用途池、约束、授权/署名）
remotion/src/effects/       # 动效移植（shotcraft Apache-2.0 手法，按风格 tokens 重新蒙皮）
assets/warehouse/     # 本地素材库（媒体文件 gitignore，只提交 README/SOURCES）
templates/<category>/project.json   # 新项目模板
templates/shots/mediastorm.example.json  # 分镜示例
templates/brief.example.json
projects/             # 各房源项目（私有，gitignore；仅 _example 提交）
  _example/           # 完整示例（二手房，示例数据）
  rental/ resale/ new-home/<YYYY-MM-DD-pinyin-id>/
voices/presets.json   # voicedesign 音色描述
voices/clone/         # 克隆参考音频（私有，gitignore）
vendor/qwentts.cpp    # git 子模块（不要随意改动）
scripts/build-tts.cmd # 编译 qwen-tts.exe（CUDA, sm_61）
docs/                 # crm.md, tts.md, new-project.md
```

### 项目文件夹约定
- 路径：`projects/<category>/<YYYY-MM-DD>-<pinyin-slug>/`，例如 `projects/rental/2026-10-03-lvcheng-2b1l`。
- 文件夹名只用小写英文/拼音/数字/连字符；**中文名写在 `project.json` 里**（`title`、`property.community` 等）。
- 子目录：`raw/`（原始素材）、`canva/`（Canva 导出卡片）、`audio/`（TTS 输出）、`consent/`（业主委托/授权书、声音授权）、`output/`（成片）。

## 3. 标准流程

1. `npm run new -- <category> <slug>` 新建项目（自动加日期前缀）。
2. 把素材放进 `raw/`、Canva 卡片放进 `canva/`、授权文件放进 `consent/`。
3. （ASR 转写：占位，尚未实现）
4. 编辑 `project.json`：房源字段 + `narration.segments`（每段 `id`、`text`、`presenter`）。
5. （可选）`npm run tts -- projects/<category>/<id>` 生成配音。
6. `npm run check -- projects/<category>/<id>`，直到 PASS。
7. `npm run render -- projects/<category>/<id> [--ratio 4x3|3x4|9x16]`。
8. 发布前自检（AI 声明、广告标注等，见 `rules/workflow.md`）。

## 3A. 一句话成片（固定工作流，优先使用）

```
npm run make -- "<一句话>" [--style mediastorm] [--ratio 4x3] [--voice edge|qwen|own] [--answer key=value ...] [--mock]
```

阶段固定、幂等：每个阶段只写自己的产物到 `projects/<cat>/<id>/`，产物已存在就跳过（`--force` 重跑）。
单独重跑：`npm run <stage> -- projects/<cat>/<id> [--force]`，或 `python pipeline/make.py --project <dir> --only <stage>`。

| # | 阶段 | 产物 | 说明 |
|---|---|---|---|
| 0 | parse | `brief.json` | 规则解析一句话；缺信息 → 打印问题并退出码 3 |
| 1 | listing:fetch | `listing.json`、`wall_candidates.json`、`raw/listing/*`、`raw/floorplan.*` | crm_connector REST（只读、白名单字段）；缺值写 `待填` 让 check 失败 |
| 2 | listing:wall | `wall.json`、`raw/wall/*` | 6–12 张卡 + picked；CRM 编号不进 wall.json（映射在 `raw/wall_map.json`） |
| 3 | map:fetch | `map/geo.json`、`map/satellite_4x3.jpg`、`map/static.png`、`map/pois.json` | map-tools skill（高德，GCJ-02）；失败时生成“示意底图” |
| 4 | assets:import | `assets/manifest.json` | 每个素材的来源/许可/水印/AI 标记 |
| 4b | effects | `effects.json` | 从 `rules/effects/catalog.json` 按用途池为每个镜头抽动效：种子=项目 id（重渲染不变），`--reseed` 重抽；同片不重复、相邻不同、每 30s ≤2 个高能；避开最近 5 条视频（`projects/.effects-history.json`，gitignore）。render 读 effects.json |
| 5 | script | `project.json` 的 `narration.segments` + `shots.json` | **Agent 按 `rules/style/mediastorm.md` 自己写**；自动生成的是确定性兜底稿（模板感重，必须改写） |
| 6 | tts | `audio/seg_*.wav`、`audio/segments.json` | edge（草稿）/ qwen（本地）/ own（自录，需 `raw/voice/seg_*.wav`） |
| 7 | check | — | 硬门槛：合规 + 隐私 PII + 素材清单/水印 + 地图署名 + 风格 |
| 8 | render | `output/<id>_<ratio>.mp4` | 先 check；固定响度归一化 mediastorm −16 LUFS |

### 必须问用户的问题（make 会列出缺的项；拿到答案用 `--answer` 回填）
> 风格固定 mediastorm（影视飓风），不需要问。
1. **分类**：租赁 / 二手房 / 新房（`--answer category=rental`）
2. **房源**：CRM 房源编号，或小区名 + 筛选（户型/租金或总价/面积/朝向）（`listing.listing_id=` / `listing.community_keyword=` / `listing.rooms=2` / `listing.monthly_rent_yuan=4000:5500`）；以及**列表墙重点讲哪一套**（`listing.pick=`）
3. **配音**：AI（edge 草稿 / qwen）还是本人录音（`voice.mode=`；自录放 `audio/seg_<段id>.wav`）；AI 声音需声音本人书面授权放 `consent/`
4. **业主委托/授权书**是否已放 `consent/`（`confirm.consent.owner`）
5. **必须公示信息**：二手房核验码、租赁房源核验/登记备案编号（按当地要求）、价格有效期、中介全称、出镜人是否认证本人（`confirm.disclosures`）
6. **flova 生图默认开启**（`flova.allowed=true`，用于地图底图重绘和装饰图；生图按用途用 GPT Image 2.5 Sunburst（成片/精修/品牌/地图重绘）或 Flare（日常/批量/社媒/试错），不生成户型/实景/景观/周边）；积分由 flova MCP 自行处理，**不是限制**；只有想关掉才写 `flova.allowed=false`。**视频生成默认关闭**（`flova.video_allowed=false`）：用户没有明确写 `flova.video_allowed=true`，Agent 一律不得调 `generate_video`，也不得生成 mp4/动态视频（含地图、装饰、转场）。
7. **要排除的照片**（有人像、门牌、水印、杂乱）（`confirm.photos.exclude`）
8. **发布平台**：抖音 / 视频号（`platform=douyin,channels`）
9. 地图是**必选项**（见 §3E）；可指定查询地点（`map.query=小区名` `map.city=杭州`）和通勤目的地（`map.commute_to=西湖文化广场`，可选）

不要替用户回答这些问题；`--mock` 只用于演示/测试，产物带“示例数据”角标。

## 3D. 审美规则与 harmony 检查（强制，所有 Agent）

1. **写 `shots.json` / 改镜头组件 / 渲染之前，必须先读 `rules/taste.md`**（taste-skill 的视频量化版：Design Read、三个 dial、反 AI 默认禁令、4:3 安全区与字幕/PiP 碰撞区、单一世界分层、字号表、动效上限）。开工前写出 Design Read 一行。
2. **渲染后**：用 `npm run still -- projects/<cat>/<id> --frame <N>` 为**至少 4 个不同镜头**出静帧，然后 `npm run check -- projects/<cat>/<id> --require-taste`（自动跑 `pipeline/check/harmony_check.py`；只跑审美检查用 `npm run check:taste -- projects/<cat>/<id>`）。
3. **硬失败（FAIL）阻断交付**：修（优先改代码）→ 重出静帧 → 重跑。软警告（WARN）在交付说明里逐条写明处理或理由。没有静帧时 check 会打印提示，**不等于通过**。
4. **必须人工看过每一张静帧**（脚本只抓回归，不判断品味；可见的接缝、水印、文字碰撞、第二层地图一律算不通过）。
5. 不得用 `--skip-taste` 绕过；只有用户明确同意时才可用，并在交付说明里写明。

## 3B. 数据源与隐私规则

**房源（crm_connector，云端 BeikeMicroservice；完整说明见 `docs/crm.md`，Word：`docs/crm.docx`）**
- 只接入租赁（二手房/新房未接）。服务在 `beike-server`（`119.29.187.184`）：systemd `crm-connector.service`，进程只监听服务器 `127.0.0.1:8020`，代码 `/opt/crm-connector/current`。
- 本机取数前先开 SSH 转发，再跑 `listing:fetch`（不必改默认 `CC_BASE_URL`，请求前缀 `{CC_BASE_URL}/api/v1`）：`ssh -N -L 8020:127.0.0.1:8020 beike-server`。不要把 8020 对公网开放。
- 流水线只调三个只读接口：`POST /api/v1/listings/rental/search`、`GET /api/v1/listings/rental/{listing_id}`、`GET /api/v1/listings/rental/{listing_id}/prospect`；MCP 业务工具限流 30 次/分钟（`CC_MCP_RATE_LIMIT_PER_MIN`）。
- 公网 `http://119.29.187.184:8080` 只转发归档看板（`/archive`）和状态（`/api/v1/archive/rental/status`），只能看归档进度，不能搜房、不能下详情。
- 返回 `CRM_AUTH_REQUIRED` = 云端会话失效，由用户在服务器上扫码，**Agent 不得代登录**。
- **禁止**读取/复制/打印 `services/crm_connector/run/*`（含 browser_state.json）、cookie、token 及服务器上的凭证；**禁止调用** `rental_listing_get_house_info` / `GET .../house-info`（含跟进人姓名电话）。
- 只保留白名单字段（见 `docs/crm.md` 第 6 节 / listing.py `ALLOWLIST`）；楼层只保留粗略楼层（低/中/高）；图片 URL 按规则加尺寸后缀（`.1500x.jpg`；已带 `.450x.jpg`/`.750x.jpg`/`.800x.jpg`/`.1500x.jpg` 后缀的不重复加）。
- CRM 实勘图带平台水印的**不能用**，也不能去水印；manifest 里 CRM 图默认 `watermarked: null`，人工确认后才改 `false`。

**地图（~/.agents/skills/map-tools/scripts/map.py）**
- `geocode|place|reverse|satellite|staticmap|panorama`，默认高德、GCJ-02。密钥在 `~/.config/map-tools/keys.json`，**不得打印/提交**。天地图在该网络被拦截。
- 地图画面必须带图源署名；公开发布的地图需核实审图号要求（待核实）。距离只写“约 N 米 · 直线距离（来源）”，**不写“步行 X 分钟”**。

**隐私（check.py 会拦截）**：人名+称谓、手机号、微信号、精确楼层（“6/18”“6层”）、楼栋/单元/室号、门牌/详细地址、CRM 编号与链接、ke.com / lianjia / 贝壳 / 链家 logo 或网址。

## 3C. flova（视频/生图 MCP）

- 仓库内 `.mcp.json`（标准 MCP，Claude Code 等读取）与 `.grok/config.toml`（Grok 读取）声明同一条 stdio server `flova-image`，它们是**项目配置**，可按任务修改。Agent **不得修改用户本机的 MCP 客户端配置**（`~/.zcode`、`~/.claude`、`~/.cursor` 等）。
- **视频（默认关闭）**：只有 brief 里 `flova.video_allowed=true`（用户明确开启）才允许调 MCP 工具 `generate_video`；默认 `false`，此时**不得**生成任何视频（地图、装饰、转场都不行），流水线也不会产出视频请求。开启后 `model` 只能是 `wan-3.0-prime`，且必须传 `reference_images`；`wan-3.0`、`minimax-h3`、`minimax-h3-max-turbo`、`gemini-omni-flash` 等其他视频模型禁止出现在请求参数里。check 会拦下 video_allowed 不是 true 时登记的 AI 视频素材和视频类地图请求。
- **生图**：MCP 工具 `generate_image`，按用途二选一——成片、精细改图、品牌/产品图用 `gpt-image-2.5-sunburst`；日常出图、批量、社媒、快速试错用 `gpt-image-2.5-flare`；禁止其他图像模型（含 `auto`、`gpt-image-2`、`nano-banana-2`、`nano-banana-pro`、`seedream-5-pro`、`seedream-4.5`、`midjourney`、`muse`）；只请求无水印原片（`original:true`，不传 `profile`）。
- **只能**生成装饰素材（光效、纹理、抽象图）和 §3E 的地图底图重绘；转场类视频只有在 `flova.video_allowed=true` 时才可生成；`generate_image` 用于地图底图重绘和片头、标识、包装类装饰图。**绝不**生成户型图、室内实景、景观、小区/周边等事实性房源画面。
- 不去水印；只请求无水印原片（`original:true`，不传 `profile`）；不调 `ensure_credits`，不写多账号/邀请刷积分脚本，不使用邀请/刷积分功能。积分由 flova MCP 自行处理，**不是限制**（不写“够做 N 条”）；生成失败（含积分原因）把错误原文告诉用户，不绕过。
- 生成后放进 `projects/<cat>/<id>/assets/flova/`，再跑 `npm run assets:import -- <dir>`，并在 `assets/manifest.json` 补齐：`source:"flova"`、`model`、`prompt`、`watermarked`、`license`、`ai:true`、`usage:"decorative"|"transition"`。check 对缺字段或 `watermarked:true` 直接失败；画面自动加“AI生成”角标，发布时勾选 AI 标注。

## 3E. 地图是必选项 + 地图底图图片重绘（Agent 执行，不生成视频）

- 房源信息几乎都和位置相关：**地图是每条视频的固定部分**，不可选、不可省。`shots.json` 的地图镜头带 `map_role`：`overview`（小区在城市/片区的位置）、`commute`（`map/route.json` 的高德路线距离/耗时）、`amenities`（`map/pois.json` 的 POI 距离）；有数据的角色都至少要有一个镜头。check：正式片缺地图镜头 = 失败，`--mock` = 提醒。
- 数字只能用高德返回值（POI 直线距离由高德坐标计算，路线来自高德路径规划）。画面只写“约 N 米 · …距离（来源）”，不写“X 分钟到”（banned_words 会拦；耗时保存在 `route.json` / 镜头 `route_ref`，仅供参考）。
- 地图脚本配置在 `config/map-tools.json`（默认 `~/.agents/skills/map-tools/scripts/map.py`，可用环境变量 `MAP_TOOLS_SCRIPT` 覆盖），默认高德、GCJ-02，密钥只放 `~/.config/map-tools/keys.json`，不进仓库。
- 署名：真实高德静帧用 `地图数据 © 高德地图（示意，非测绘成果）`；AI 重绘底图必须用 `示意图 / AI 生成底图 / © 高德地图`；没取到高德数据的示意底图用 `示意图 / 示意底图（非真实地图）/ © 高德地图`；由 map:fetch 写入 `map/geo.json.attribution`，check 会核对。
- flova 默认开启，积分**不是限制**：brief 里没有 `credit_budget`（旧 brief 里有也会被忽略）。生成失败（包括积分原因）→ 把错误原文告诉用户，不绕过；不使用邀请/多账号/刷积分。
- 需要重绘时是 **Agent 步骤**（仓库 Python 调不了 MCP），流程是原来的“图片重绘”：高德静态图 `map/static.png` → flova 图像生成 → 无水印原图存成 `map/base_ai.png` → 代码叠标签/距离：
  1. 跑 `npm run make -- ...`（或 `npm run map:fetch -- <项目>`）到 map:fetch：写 `map/flova_request.json`（`tool=generate_image`、`model=gpt-image-2.5-sunburst`、`prompt`、`source_image=map/static.png`、`output_image=map/base_ai.png`、`params={profile:"kid4", original:true}`），`map/base_ai.png` 不存在时退出码 3 并打印说明。
  2. 调 flova-image 的 `generate_image`（gpt-image-2.5 系列，见 `config/flova-models.json`）：`prompt=request.prompt`，参考图传 `map/static.png` 的绝对路径，参数 `profile="kid4"`、`original=true`。**不要调 `generate_video`，地图不用视频动画。**
  3. 把返回的无水印原图存成 `<项目>/map/base_ai.png`。
  4. 原命令重跑：幂等地把它转成 `map/satellite_4x3.jpg`（原高德卫星图备份为 `map/amap_satellite_4x3.jpg`），`geo.json` 写 `base=ai_repaint`、`repaint.status=done`、署名改为 `示意图 / AI 生成底图 / © 高德地图`；再跑 `npm run assets:import -- <dir> --force` 把底图登记成 AI 素材（ai:true、decorative）。check 在 `repaint.status=pending` 时报未完成。
  - `--mock`、`flova.allowed=false` 或没取到高德数据时不走这一步：用带标注的示意底图（或高德原图）；关掉重绘且 `map/amap_satellite_4x3.jpg` 还在时会把原图拷回卫星图。
- **视频生成默认关闭**：`brief.flova.video_allowed` 默认 `false`（`normalize_flova` 会把非 `true` 的值都矫正为 `false`）。没有用户明确写 `flova.video_allowed=true`，不得调 `generate_video`、不得生成 mp4（含装饰/转场）；地图永远只走上面的图片重绘。

## 4. 固定命令（Agent 只用这些入口，不要自造等价命令）

| 命令 | 作用 |
|---|---|
| `npm run new -- rental lvcheng-2b1l [--date 2026-10-03]` | 新建项目 |
| `npm run tts -- projects/rental/<id> [--voice narrator_male_30] [--dry-run]` | 分段 TTS，写 `audio/segments.json` |
| `npm run check -- projects/rental/<id>` | 合规检查，失败返回非 0 |
| `npm run render -- projects/rental/<id> [--ratio 4x3\|3x4\|9x16]` | 先 check，再渲染到 `output/<id>_<ratio>.mp4` |
| `npm run still -- projects/rental/<id> [--ratio 4x3] [--frame 220]` | 渲染单帧 PNG（快速验证） |
| `npm run check:taste -- projects/rental/<id>` | 只跑静帧 harmony 审美检查（§3D）；`check --require-taste` = 合规 + 审美 |
| `npm run preview -- projects/rental/<id>` | Remotion Studio 预览 |
| `npm run make -- "<一句话>" [--style mediastorm] [--ratio 4x3] [--mock]` | 一句话成片（§3A） |
| `npm run listing:fetch -- <dir>` / `listing:wall` / `map:fetch` / `assets:import` / `script` / `voice` | 单独重跑某阶段（加 `--force` 覆盖） |
| `npm run effects -- <dir> [--reseed [N]] [--force]` | 重抽/重算本片动效（写 effects.json；改完需重渲染） |
| `npm run setup` | 安装 remotion/ 依赖 |
| `npm run typecheck` | `tsc --noEmit` |
| `scripts\build-tts.cmd` | 编译 qwen-tts.exe（只有用户要求时才运行） |

## 5. 硬性禁止

1. **不得 push** 到 GitHub、不得改 remote、不得强推/改写已有提交，除非用户明确要求。
2. **不得提交私有素材**：`projects/` 下除 `_example` 外全部 gitignore；不要用 `git add -f` 绕过。`voices/clone/`、`.env` 同理。
3. **不得绕过合规检查**：`render` 必须先通过 `check`；不要给 check 加跳过开关，不要为了通过而删违禁词表条目。修文案，不修规则。
4. **不得编造房源信息或法规**：价格、面积、核验码、预售证号等只能来自用户提供的资料；缺失就留 `待填` 让 check 失败。规则中未核实的内容标注 `待核实`。
5. **画面/口播/字幕/封面中不得出现**：电话、微信号、二维码、网址、站外平台 logo、“私信领资料/获取底价”。
6. **不得使用**绝对化用语、升值/投资回报承诺、学区/落户承诺、“X分钟到地铁”式时间表述、风水迷信、零首付/首付分期/售后包租等（完整列表见 `rules/compliance/common.md` 与 `pipeline/check/banned_words.json`）。
7. **不得模板化批量出片**：视频号公约禁止脚本雷同、表现形式高度一致的视频。每条视频的口播、镜头、节奏要真正不同（见 `rules/style.md`）。
8. **不得随意改动 `vendor/qwentts.cpp`**（子模块）；不要擅自编译或下载大模型，除非用户要求。
9. **不得在仓库外写文件**（读取可以）。
10. **不得提交** `projects/`（除 `_example`）、`assets/warehouse/` 媒体文件、`.env`、地图密钥、CRM 登录态或任何 token。
11. 不得读取 crm_connector `run/*`、cookie、token；不得调用 house-info；不得修改用户本机 MCP 客户端配置（仓库内 `.mcp.json` / `.grok/config.toml` 是项目配置，不在此列）；不得用 AI 生成事实性房源画面。
12. AI 配音/克隆必须有本人书面授权（放 `consent/` 或 `voices/clone/`），并在发布时勾选 AI 标注。

## 6. 规则索引（改代码或写文案前先读）

- `rules/compliance/common.md` — 通用合规（所有分类）
- `rules/compliance/rental.md` / `resale.md` / `new-home.md` — 分类专项
- `rules/style.md` — 视觉风格、节奏、镜头效果
- `rules/style/mediastorm.md` — 影视飓风风格预设（测量值、组件用法）
- `rules/taste.md` — **审美规则 + 渲染后 harmony 检查（写分镜/渲染前必读，§3D）**（许可证：`rules/LICENSE-taste-skill.txt`）
- `docs/one-sentence-workflow.md`（给用户的版本：`docs/one-sentence-workflow.docx`）
- `docs/crm.md` — 云端 CRM 与本项目取数（Word：`docs/crm.docx`）
- `rules/workflow.md` — 流程与发布前自检
- `rules/reference/` — 原始调研（含全部来源链接）
- `docs/tts.md`、`docs/new-project.md`

## 7. 编码约定

- 所有文本文件 UTF-8（JSON/Python/TS 无 BOM），换行 LF。Windows 上写文件用 Python `open(..., encoding="utf-8", newline="\n")`，不要用 PowerShell 5 的 `Set-Content`/`Out-File` 默认编码。
- Python 尽量只用标准库；需要第三方包时加 `requirements.txt`，只装进仓库内 `.venv`，不要全局 pip install。
- Remotion 代码必须通过 `npm run typecheck`。新增字段要同步：`templates/` → `pipeline/schema/` → `remotion/src/types.ts` → `check.py`（`style` 字段即按此同步）。
- 给用户看的文档必须是 .docx 或 .pdf（仓库内保留 .md 源）。
- 字体只用可免费商用的，并把许可证放在字体旁（`remotion/src/assets/fonts/README.md`）。
- 提交信息用英文。
