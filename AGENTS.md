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
remotion/src/styles/  # 风格预设 tokens：qiuzhi.ts / mediastorm.ts + fonts.ts
remotion/src/shots/   # 共用镜头组件：ListingWall RoomCard FloorplanLocator LocationLabel SpecCard DataNumber MapReveal ShotVideo
remotion/src/assets/fonts/  # 可商用字体 + 许可证（README.md）
rules/style/<preset>.md     # 各风格预设的测量规则（写脚本/分镜前必读）
rules/effects/              # 动效目录 catalog.json + README（用途池、约束、授权/署名）
remotion/src/effects/       # 动效移植（shotcraft Apache-2.0 手法，按风格 tokens 重新蒙皮）
assets/warehouse/     # 本地素材库（媒体文件 gitignore，只提交 README/SOURCES）
templates/<category>/project.json   # 新项目模板
templates/shots/<style>.example.json  # 分镜示例
templates/brief.example.json
projects/             # 各房源项目（私有，gitignore；仅 _example 提交）
  _example/           # 完整示例（二手房，示例数据）
  rental/ resale/ new-home/<YYYY-MM-DD-pinyin-id>/
voices/presets.json   # voicedesign 音色描述
voices/clone/         # 克隆参考音频（私有，gitignore）
vendor/qwentts.cpp    # git 子模块（不要随意改动）
scripts/build-tts.cmd # 编译 qwen-tts.exe（CUDA, sm_61）
docs/                 # tts.md, new-project.md
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
npm run make -- "<一句话>" [--style qiuzhi|mediastorm] [--ratio 4x3] [--voice edge|qwen|own] [--answer key=value ...] [--mock]
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
| 5 | script | `project.json` 的 `narration.segments` + `shots.json` | **Agent 按 `rules/style/<preset>.md` 自己写**；自动生成的是确定性兜底稿（模板感重，必须改写） |
| 6 | tts | `audio/seg_*.wav`、`audio/segments.json` | edge（草稿）/ qwen（本地）/ own（自录，需 `raw/voice/seg_*.wav`） |
| 7 | check | — | 硬门槛：合规 + 隐私 PII + 素材清单/水印 + 地图署名 + 风格 |
| 8 | render | `output/<id>_<ratio>.mp4` | 先 check；按风格做响度归一化（mediastorm −16 / qiuzhi −17 LUFS） |

### 必须问用户的问题（make 会列出缺的项；拿到答案用 `--answer` 回填）
1. **分类**：租赁 / 二手房 / 新房（`--answer category=rental`）
2. **房源**：CRM 房源编号，或小区名 + 筛选（户型/租金或总价/面积/朝向）（`listing.listing_id=` / `listing.community_keyword=` / `listing.rooms=2` / `listing.monthly_rent_yuan=4000:5500`）；以及**列表墙重点讲哪一套**（`listing.pick=`）
3. **风格**：qiuzhi / mediastorm（`style=`）
4. **配音**：AI（edge 草稿 / qwen）还是本人录音（`voice.mode=`；自录放 `audio/seg_<段id>.wav`）；AI 声音需声音本人书面授权放 `consent/`
5. **业主委托/授权书**是否已放 `consent/`（`confirm.consent.owner`）
6. **必须公示信息**：二手房核验码、租赁房源核验/登记备案编号（按当地要求）、价格有效期、中介全称、出镜人是否认证本人（`confirm.disclosures`）
7. **是否允许 flova** 生成装饰/转场片段 + 积分预算（`flova.allowed=true` `flova.credit_budget=50`）
8. **要排除的照片**（有人像、门牌、水印、杂乱）（`confirm.photos.exclude`）
9. **发布平台**：抖音 / 视频号（`platform=douyin,channels`）
10. 可选：地图查询地点（`map.query=小区名` `map.city=杭州`）

不要替用户回答这些问题；`--mock` 只用于演示/测试，产物带“示例数据”角标。

## 3B. 数据源与隐私规则

**房源（crm_connector，BeikeMicroservice/services/crm_connector）**
- 只读。REST `http://127.0.0.1:8020/api/v1`（`CC_BASE_URL` 可改）或 MCP `crm-connector`（工具 `rental_listing_search` / `rental_listing_get_detail` / `rental_listing_get_prospect` 等）。限流 30 次/分钟。
- 返回 `CRM_AUTH_REQUIRED` = 用户需要扫码登录（`crm-authd login`），**Agent 不得代登录**。
- **禁止**读取/复制/打印 `services/crm_connector/run/*`（含 browser_state.json）、cookie、token。
- **禁止调用** `rental_listing_get_house_info`（含跟进人姓名电话）。
- 只保留白名单字段（listing.py `ALLOWLIST`）；楼层只保留粗略楼层（低/中/高）；图片 URL 必须加尺寸后缀（`.1500x.jpg`）否则 403。
- CRM 实勘图带平台水印的**不能用**，也不能去水印；manifest 里 CRM 图默认 `watermarked: null`，人工确认后才改 `false`。

**地图（~/.agents/skills/map-tools/scripts/map.py）**
- `geocode|place|reverse|satellite|staticmap|panorama`，默认高德、GCJ-02。密钥在 `~/.config/map-tools/keys.json`，**不得打印/提交**。天地图在该网络被拦截。
- 地图画面必须带图源署名；公开发布的地图需核实审图号要求（待核实）。距离只写“约 N 米 · 直线距离（来源）”，**不写“步行 X 分钟”**。

**隐私（check.py 会拦截）**：人名+称谓、手机号、微信号、精确楼层（“6/18”“6层”）、楼栋/单元/室号、门牌/详细地址、CRM 编号与链接、ke.com / lianjia / 贝壳 / 链家 logo 或网址。

## 3C. flova（图片/视频生成 MCP）

- 目前只在 ZCode 注册（`~/.zcode/cli/config.json`，server `flova-image`，`node C:/Users/shipi/.flova-mcp/server.js`）。**Agent 不得修改任何客户端配置**；用户想在 Codex / Claude Code / OpenCode 用，需要自己注册同一 server。
- **只能**生成装饰/转场素材（光效、纹理、抽象转场）。**绝不**生成户型图、室内实景、景观、小区/周边等事实性房源画面。
- 不去水印；用 `original:false` 或付费套餐无水印输出；不写多账号/邀请刷积分脚本；遵守用户给的积分预算。
- 生成后放进 `projects/<cat>/<id>/assets/flova/`，再跑 `npm run assets:import -- <dir>`，并在 `assets/manifest.json` 补齐：`source:"flova"`、`model`、`prompt`、`watermarked`、`license`、`ai:true`、`usage:"decorative"|"transition"`。check 对缺字段或 `watermarked:true` 直接失败；画面自动加“AI生成”角标，发布时勾选 AI 标注。

## 4. 固定命令（Agent 只用这些入口，不要自造等价命令）

| 命令 | 作用 |
|---|---|
| `npm run new -- rental lvcheng-2b1l [--date 2026-10-03]` | 新建项目 |
| `npm run tts -- projects/rental/<id> [--voice narrator_male_30] [--dry-run]` | 分段 TTS，写 `audio/segments.json` |
| `npm run check -- projects/rental/<id>` | 合规检查，失败返回非 0 |
| `npm run render -- projects/rental/<id> [--ratio 4x3\|3x4\|9x16]` | 先 check，再渲染到 `output/<id>_<ratio>.mp4` |
| `npm run still -- projects/rental/<id> [--ratio 4x3] [--frame 220]` | 渲染单帧 PNG（快速验证） |
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
11. 不得读取 crm_connector `run/*`、cookie、token；不得调用 house-info；不得修改 flova/MCP 客户端配置；不得用 AI 生成事实性房源画面。
12. AI 配音/克隆必须有本人书面授权（放 `consent/` 或 `voices/clone/`），并在发布时勾选 AI 标注。

## 6. 规则索引（改代码或写文案前先读）

- `rules/compliance/common.md` — 通用合规（所有分类）
- `rules/compliance/rental.md` / `resale.md` / `new-home.md` — 分类专项
- `rules/style.md` — 视觉风格、节奏、镜头效果
- `rules/style/mediastorm.md`、`rules/style/qiuzhi.md` — 风格预设（测量值、组件用法）
- `docs/one-sentence-workflow.md`（给用户的版本：`docs/one-sentence-workflow.docx`）
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
