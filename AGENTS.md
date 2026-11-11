# AGENTS.md — ReelEstate 所有编码 Agent 的总规则

> 适用于 Codex、Claude Code、OpenCode、Grok 及任何在本仓库工作的 Agent。`CLAUDE.md` 只引用本文件。
> 文档/规则用中文写，代码、标识符、文件夹名用英文（或拼音）。
> 现行生产入口：`docs/PRODUCTION.md`（先 `npm run doctor`），架构：`docs/architecture.md`，期内目录：`docs/FOOTAGE-SPEC.md`。
> 2026-10-30 用户要求只保留最新架构：旧 project.json 工程、`npm run make` 一句话成片阶段、`projects/<category>/`、`projects/map-hub` 联接均已退役，不要恢复。

## 1. 项目目的

为一位中国房产视频创作者（抖音 + 微信视频号）制作**科普/讲解风格**的视频：房源讲解（rental 租赁 / resale 二手房 / new-home 新房）、知识口播、小ONE会客厅。
真人或 HeyGen 数字人口播 + Remotion 动效 + 地图 + 克隆配音（本人授权）。

按用户于 2026-10-31 的明确要求，**本项目仅用于非商业用途**。房源类、知识类和小ONE会客厅的素材选型、第三方代码与服务接入均按非商业用途处理；允许使用符合其非商业条款的素材或代码（包括 CC BY-NC 等许可），不要求额外取得商用授权，不得仅因不允许商用或缺少商用授权而排除候选或阻断制作。署名、修改、再分发、来源记录、API 使用条件和服务费用仍按各自条款执行。 细则见 `docs/CONVENTIONS-shared.md` §0；所有 Agent 接手时沿用这一项目用途。

- 默认导出：**4:3 横版 1440×1080 @30fps**。
- 合规是硬约束：视频号《房地产行业公约》（2026-05-12 生效）、《广告法》、《房地产广告发布规定》、《住房租赁条例》等。见 `rules/compliance/`。

## 2. 目录结构

```
AGENTS.md / CLAUDE.md / README.md / package.json（npm scripts 是固定入口）
pipeline/video.py          # 统一 CLI：new / check / render / still / restore / manifest / episodes / doctor ...
pipeline/common/           # 公共能力：workspace、episodes、sync_assets、color_restore、raw_manifest、crm_listing、heygen_plan ...
pipeline/maphub/           # 房源流水线（amap_fetch、build_vo、check_episode、render_episode、track_annotations ...）
pipeline/knowledge/        # 知识口播流水线
pipeline/interview/        # 小ONE会客厅流水线
pipeline/check/            # 发布合规检查 check.py（读 compliance.json + data/timeline.json）、harmony 审美检查
pipeline/schema/           # compliance.json 的 JSON Schema（common + rental / resale / new-home）
templates/listing/         # 房源新建模板 episode.json + compliance.example.json
templates/map-hub/remotion # 房源镜头编排（map-hub 是模板名）；templates/knowledge、templates/interview 同理
templates/shared/          # 公共 Remotion 组件与字体/品牌素材
tools/remotion/            # 唯一的 Node 依赖
scripts/                   # new_episode、make-video、voice、matting、kaggle、flova
assets/                    # 共享素材：presenter、luts/pocket3、brands
rules/                     # 合规、风格、审美、flova 规则
docs/                      # PRODUCTION、architecture、FOOTAGE-SPEC、各 RUNBOOK
projects/listing/epNN-<slug>/   # 房源期（category 写在 episode.yaml）；projects/listing/_sources/ 放未建期的原始资料
projects/knowledge/epNN-<slug>/ # 知识期
projects/interview/epNN-<slug>/ # 会客厅期
voices/clone/              # 克隆参考音频（私有，只读）
```

### 期内目录（房源，详见 docs/FOOTAGE-SPEC.md）
- 文件夹名 `epNN-<pinyin>`，只用小写字母/数字/连字符；中文名、类别、户型、房源编号写在 `episode.yaml`，不进目录名。
- `footage/raw/` 原片只读（保留相机原名），对应关系写 `footage/raw_manifest.json`；还原输出 `footage/restored/{master,proxy}/`；模板镜头 `footage/shots/<ID>.mp4`；采用的静态素材 `footage/assets/`；高德原始返回 `sources/amap/`；新房开发商资料 `sources/docs/`。
- 发布资料是 `compliance.json`（新建时为 `.draft`），实际旁白以 `data/timeline.json` 为准。没有 `project.json`。

## 3. 标准流程

1. `npm run doctor`，`npm run episodes`（下一发布号）。
2. 建期（Agent 执行，见下方「做视频」）：`npm run new -- rental|resale|new-home <slug> ...`，知识/会客厅见各自 runbook。
3. 实拍素材：只复制进 `footage/raw/` → `npm run manifest -- <ep> --init` → `npm run restore -- <ep>`（Pocket 3 D-Log M 自动还原）。
4. 按 `docs/RUNBOOK-map-hub-koubo.md`（房源）/ `RUNBOOK-knowledge-koubo.md` / `RUNBOOK-interview.md` 逐阶段推进，更新 `episode.yaml` 的 `status`。
5. `npm run check -- <ep> --draft` → 草稿 `npm run render -- <ep> --draft --ver <v>`。
6. 正式：填好 `compliance.json`，`npm run check -- <ep>` 通过后 `npm run render -- <ep> --platform shipinhao`；静帧审美检查见 §3D；人工审片。

## 3D. 审美规则与 harmony 检查（强制，所有 Agent）

1. **写 `shots.json` / 改镜头组件 / 渲染之前，必须先读 `rules/taste.md`**（taste-skill 的视频量化版：Design Read、三个 dial、反 AI 默认禁令、4:3 安全区与字幕/PiP 碰撞区、单一世界分层、字号表、动效上限）。开工前写出 Design Read 一行。
2. **渲染后**：用 `npm run still -- <ep> --draft --frame <N> --ver review` 为**至少 4 个不同镜头**出静帧，然后 `npm run check:taste -- <ep> --ver review`（跑 `pipeline/check/harmony_check.py`）。
3. **硬失败（FAIL）阻断交付**：修（优先改代码）→ 重出静帧 → 重跑。软警告（WARN）在交付说明里逐条写明处理或理由。没有静帧时 check 会打印提示，**不等于通过**。
4. **必须人工看过每一张静帧**（脚本只抓回归，不判断品味；可见的接缝、水印、文字碰撞、第二层地图一律算不通过）。
5. 不得用 `--skip-taste` 绕过；只有用户明确同意时才可用，并在交付说明里写明。

## 3B. 数据源与隐私规则

**房源（crm_connector，云端 BeikeMicroservice；完整说明见 `docs/crm.md`，Word：`docs/crm.docx`）**
- 只接入租赁（二手房/新房未接）。服务在 `beike-server`（`119.29.187.184`）：systemd `crm-connector.service`，进程只监听服务器 `127.0.0.1:8020`，代码 `/opt/crm-connector/current`。
- 本机取数前先开 SSH 转发，再跑 `python pipeline/common/crm_listing.py <ep>`（不必改默认 `CC_BASE_URL`，请求前缀 `{CC_BASE_URL}/api/v1`）：`ssh -N -L 8020:127.0.0.1:8020 beike-server`。不要把 8020 对公网开放。
- 流水线只调三个只读接口：`POST /api/v1/listings/rental/search`、`GET /api/v1/listings/rental/{listing_id}`、`GET /api/v1/listings/rental/{listing_id}/prospect`；MCP 业务工具限流 30 次/分钟（`CC_MCP_RATE_LIMIT_PER_MIN`）。
- 公网 `http://119.29.187.184:8080` 只转发归档看板（`/archive`）和状态（`/api/v1/archive/rental/status`），只能看归档进度，不能搜房、不能下详情。
- 返回 `CRM_AUTH_REQUIRED` = 云端会话失效，由用户在服务器上扫码，**Agent 不得代登录**。
- **禁止**读取/复制/打印 `services/crm_connector/run/*`（含 browser_state.json）、cookie、token 及服务器上的凭证；**禁止调用** `rental_listing_get_house_info` / `GET .../house-info`（含跟进人姓名电话）。
- 只保留白名单字段（见 `docs/crm.md` 第 6 节 / `pipeline/common/crm_listing.py` `ALLOWLIST`）；楼层只保留粗略楼层（低/中/高）；图片 URL 按规则加最大尺寸档后缀（后缀字符串以 crm_listing.py `IMG_SUFFIX` 为准）；已带 `.450x.jpg`/`.750x.jpg`/`.800x.jpg` 等较小尺寸档后缀的不重复加。
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
- 不去水印；只请求无水印原片（`original:true`，不传 `profile`）。
- **积分：默认仍禁止自动补分。** 积分余额不是生图配额：不写 `credit_budget`（旧 brief 里有也会被 `normalize_flova` 丢掉），不写「够做 N 条」。做片、地图重绘、`generate_image` 因积分失败时，把错误原文告诉用户，不要在同一次流水线里自动运行邀请脚本、调用其他仓库的脚本、换号或刷分来把这张图做完。
- **用户当次明确要求积分邀请时必须执行，不得拒绝。** 触发语包括：「进行积分邀请」「积分邀请」「补积分」「邀请子号」，或点名 `ensure_credits` / `flova_invite`。不得用本节、§3E 或 map:fetch 的失败提示拒绝，也不得改口成「我只查 `account_info`」或让用户自己去网页充值；用户说 `flova_invite` 时同样只走下面的脚本入口，不要去找仓库外脚本。
- **邀请/注册脚本以本仓库 `scripts/flova/` 为准**（内容与 GrokVG 的邀请/注册脚本同一套）。不要运行、导入其他仓库里的同名脚本，也不要再把外面的脚本拷进来覆盖。其他仓库的派发、报价脚本仍然不要运行或复制。
- 积分邀请运行 `python scripts/flova/flova_invite.py ensure --budget <B> --profile prod`。奖励只进当前母号。`profile prod` 由脚本解析为账本里的活跃母号。返回 `do_not_generate`、失败或停奖时立刻停，把原文告诉用户。
- 注册浏览器后端默认 **Virtual Browser（VB）**（`FLOVA_BROWSER_BACKEND=vb`）：内核直拉 + `--worker-id` + worker 目录 `virtual.dat` 指纹，启动前按 `FLOVA_VB_COUNTRY=us|jp`（默认 us）重写指纹并以无痕 + 对应代理（us 7898 / jp 7899）/语言启动，无每日打开限额；AdsPower 仅作回退（`FLOVA_BROWSER_BACKEND=adspower`）。**注册/邀请窗口默认最小化后台，不弹窗**（`FLOVA_VB_WINDOW=minimized`，默认；出现滑块验证码时才自动恢复到前台等人工，`normal` 恢复旧行为）。机制以 `docs/virtual-browser-backend.md` 和 `rules/flova-register.md` 第 2 节为准。
- 积分获取、选号、清号、接班的操作经验以 `rules/flova-credits.md` 和 `config/flova-credits-policy.json` 为准；用户当次提出这些要求时先读这两份再执行。用户当次说「注册」或「注册子号」时，同时读 `rules/flova-register.md`，跑 `scripts/flova`，不要手点一套平行流程。
- 个人账号之间不能转积分。邀请码、单次奖励、名额上限一律以工具返回为准，不写死、不写进项目文件或 git；余额用 MCP `account_info` 实时查，不写进文件。
- 调用里已经写了 `profile`，或已有 `project_id`，就钉死该号、不换号；地图重绘的 profile 钉为**当前活跃母号**（`~/.flova/registry.json` 的 `active_mother_profile`；`map/flova_request.json` 里已写的非空 `params.profile` 沿用、不换号），make / map:fetch 过程中不换号，邀请操作也不要改掉它。
- 用户没给预算时，先按 `rules/flova-credits.md` 用 `account_info` 和策略计算；仍然不知道要补多少再问一个数字，问完再调；不要因为没预算就拒绝，也不要去其他仓库跑报价脚本。
- 凭证、token、cookie 不进对话、不进 git、不进命令行、不进项目文件；不手改凭证 YAML。
- 这是用户发起的账号操作，与「流水线失败后不自动邀号」同时成立。
- 生成后放进本期 `footage/assets/`（地图底图放 `footage/assets/map/`），在同目录 README 或 `sources.md` 记下 `source:"flova"`、`model`、`prompt`、`watermarked`、`license`、`ai:true`、`usage`；画面加“AI生成”角标，发布时勾选 AI 标注。

## 3E. 地图是必选项 + 地图底图图片重绘（Agent 执行，不生成视频）

- 地图是每条房源视频的固定部分。POI 与路线距离只用高德返回值：`python pipeline/maphub/amap_fetch.py <ep>/episode.json`，写 `pois.json`，原始路线在 `sources/amap/route_*.json`。
- 画面只写“约 N 米 · …距离（来源）”，不写“X 分钟到”（banned_words 会拦）。地图脚本配置 `config/map-tools.json`，密钥只放 `~/.config/map-tools/keys.json`，不进仓库、不打印。
- 署名：真实高德底图 `地图数据 © 高德地图（示意，非测绘成果）`；AI 重绘底图 `示意图 / AI 生成底图 / © 高德地图`；示意底图 `示意图 / 示意底图（非真实地图）/ © 高德地图`。
- 重绘是 Agent 步骤：高德静态图 → flova `generate_image`（gpt-image-2.5 系列，`original:true`）→ 无水印原图存进 `footage/assets/map/`，代码叠标签。请求里已写非空 `params.profile` 时沿用，不换号；没写的交给 MCP 号池（`pipeline/common/map_profile.py`）。**不要调 `generate_video`。**
- 生成失败（包括积分）→ 把错误原文告诉用户，不绕过；做片流程里不自动邀号；用户当次明确说「进行积分邀请」时按 §3C 执行。

## 3F. DaVinci Resolve MCP（增稳等 Resolve 桌面操作）

- 集成了 `davinci-resolve-mcp` 4.17.0（上游 github.com/samuelgursky/davinci-resolve-mcp，MIT），项目 MCP 名 `davinci-resolve`，配置见 `.mcp.json`，安装在 `tools/davinci-resolve-mcp/`（node_modules 与 runtime/venv 不入库）。完整说明：`docs/davinci-resolve-mcp.md`。
- 本机是**免费版 Resolve 21.0.4.5**，外部脚本禁用，靠 in-app bridge：每次启动 Resolve 并进入工程后，必须手动 **Workspace ▸ Scripts ▸ resolve_bridge**（监听 127.0.0.1:49632），MCP 自动走 bridge；Resolve 重启需重开。
- **增稳**：`timeline_item_color(action="stabilize", track_type="video", track_index=1, item_index=N)` 可触发 Stabilizer 分析（自动归档调色版本）；但本免费版 build 的 `StabilizationEnable/Method/Strength` 脚本属性不可写（Get 返回 null、Set false），**开启与参数需人在 Inspector 点一次**（或 computer-use 代点），不要反复尝试脚本写入或魔改 Resolve。测试：`python -I tools/davinci-resolve-mcp/test/stabilize_test.py`。
- 不替代 Remotion 流水线；源素材不可变，增稳输出写新文件，不动 `footage/raw/`。bridge token 在 `~/.config/davinci-resolve-mcp/bridge.json`，不进 git、不贴对话。

## 4. 固定命令（Agent 只用这些入口，不要自造等价命令）

| 命令 | 作用 |
|---|---|
| `npm run doctor [-- <ep> --draft]` | 只读环境与本期预检 |
| `npm run episodes` | 列出各期与下一发布号 |
| `npm run new -- rental\|resale <slug> --listing <id> --title <小区名>` / `npm run new -- new-home <slug> --title <楼盘名> [--footage <dir>]` | 新建房源期（knowledge / interview 同一入口转发） |
| `npm run manifest -- <ep> [--init]` | 生成/校验 `footage/raw_manifest.json`（原片 → 房间/镜头/入出点） |
| `npm run restore -- <ep>` / `npm run restore -- --scan <dir>` | D-Log M 识别与还原（master ProRes + proxy H.264）；`--gate` 只跑门槛 |
| `npm run video:stage -- <ep>` | 准备本期 `work/remotion` |
| `npm run check -- <ep> [--draft]` | 技术预检 + 色彩门槛 + raw 清单；正式片还跑 compliance 检查 |
| `npm run still -- <ep> --draft --frame <N> --ver <v>` / `npm run render -- <ep> [--draft --ver <v>] [--platform shipinhao]` | 静帧 / 渲染（先预检，输出 `out/drafts`、`out/release`） |
| `npm run check:taste -- <ep> --ver <v>` | 静帧 harmony 审美检查（§3D） |
| `npm run setup` / `npm run typecheck` | 共用 Node 依赖与工作区 / `tsc --noEmit` |
| `npm run storage:audit` / `npm run storage:compact -- <ep> [--apply]` | 空间审计与无损压缩（不碰 raw/consent） |
| `python pipeline/common/crm_listing.py <ep>` | 租赁房源只读取数（先开 SSH 转发，§3B） |
| `python scripts/voice/push_indextts25.py --episode <ep> --script <ep>/voice/narration.json` | 口播克隆优先走这条（Kaggle 一张 T4，IndexTTS-2.5，fp32）。下载：`python scripts/kaggle/pull_job.py --episode <ep> --job tts --run indextts25` |
| `python scripts/kaggle/push_job.py --episode <dir> --job upscale --kernel seedvr2_v9 --inputs <mp4>` | 视频超分只用这个入口（V9，1280×720@24 → 1920×1080）。输出在 `kaggle/upscale/<run>/output/` |

## 5. 硬性禁止

1. **不得 push** 到 GitHub、不得改 remote、不得强推/改写已有提交，除非用户明确要求。
2. **不得提交私有素材**：`projects/` 全部 gitignore；不要用 `git add -f` 绕过。`voices/clone/`、`.env` 同理。
3. **不得绕过合规检查**：正式 `render` 必须先通过 `check`；不要给 check 加跳过开关，不要为了通过而删违禁词表条目。修文案，不修规则。
4. **不得编造房源信息或法规**：价格、面积、核验码、预售证号等只能来自用户提供的资料；缺失就留 `待填` 让 check 失败。规则中未核实的内容标注 `待核实`。
5. **画面/口播/字幕/封面中不得出现**：电话、微信号、二维码、网址、站外平台 logo、“私信领资料/获取底价”。
6. **不得使用**绝对化用语、升值/投资回报承诺、学区/落户承诺、“X分钟到地铁”式时间表述、风水迷信、零首付/首付分期/售后包租等（完整列表见 `rules/compliance/common.md` 与 `pipeline/check/banned_words.json`）。
7. **不得模板化批量出片**：视频号公约禁止脚本雷同、表现形式高度一致的视频。每条视频的口播、镜头、节奏要真正不同（见 `rules/style.md`）。
8. **不得随意改动 `vendor/`** 下的引擎；不要擅自编译或下载大模型，除非用户要求。
9. **不得在仓库外写文件**（读取可以）；用户当次明确要求的 flova 加号、清号，只用本机 flova CLI，凭证仍只在 `~/.flova` 和浏览器配置目录；注册与邀请结束后默认 profile 是 `prod`（脚本会执行 `profile use prod`）。注册只更新 `~/.flova/registry.json` 的引用和状态，不写 token 或 cookie。
10. **不得提交** `projects/`、`assets/warehouse/` 媒体文件、`.env`、地图密钥、CRM 登录态或任何 token。
11. 不得读取 crm_connector `run/*`、cookie、token；不得调用 house-info；不得修改用户本机 MCP 客户端配置（仓库内 `.mcp.json` / `.grok/config.toml` 是项目配置，不在此列）；不得用 AI 生成事实性房源画面。
12. AI 配音/克隆必须有本人书面授权（放 `consent/` 或 `voices/clone/`），`compliance.json` 标 `ai_voice: true`，发布时勾选 AI 标注。
14. **原片只读**：`footage/raw/`、SD 卡/U 盘只复制，不改名、不移动、不删除；清理只能“移走并留 manifest”，不硬删。
13. **不得运行、导入或复制其他 git 仓库的代码**（包括本机其他仓库，如 vswp 目录下的其他项目）；本仓库 npm scripts、本仓库已声明的 MCP、规则里点名的 map-tools 脚本不在此列。本仓库 `scripts/flova/` 是邀请/注册的唯一入口，不要去执行其他仓库的 `flova_invite.py`。

## 6. 规则索引（改代码或写文案前先读）

- `docs/PRODUCTION.md` — 现行生产交接（发布前自检在「正式输出」）
- `docs/architecture.md` — 架构、编号、存储与验证入口
- `docs/FOOTAGE-SPEC.md` — 期内目录、原片命名与 raw_manifest、D-Log M 还原
- `docs/CONVENTIONS-shared.md` — 三类内容共用规范
- `rules/compliance/common.md` + `rental.md` / `resale.md` / `new-home.md` — 合规
- `rules/style.md`、`rules/style/mediastorm.md`、`rules/motion.md` — 视觉风格与动效
- `rules/taste.md` — **审美规则 + 渲染后 harmony 检查（§3D）**（许可证：`rules/LICENSE-taste-skill.txt`）
- `docs/crm.md` — 云端 CRM 与取数（Word：`docs/crm.docx`）
- `rules/flova-credits.md`、`rules/flova-register.md` — 积分邀请、注册（实现在 `scripts/flova/`）
- `rules/reference/` — 原始调研（含全部来源链接）
- `docs/kaggle-gpu.md`（操作清单 `docs/TASK-kaggle.md`）、`docs/matting.md`、`docs/voice-clone.md`
- `docs/davinci-resolve-mcp.md` — DaVinci Resolve MCP 集成与增稳（免费版 bridge、stabilize 分析可脚本化、开关/参数走 GUI）

## 7. 编码约定

- 所有文本文件 UTF-8（JSON/Python/TS 无 BOM），换行 LF。Windows 上写文件用 Python `open(..., encoding="utf-8", newline="\n")`，不要用 PowerShell 5 的 `Set-Content`/`Out-File` 默认编码。
- Python 尽量只用标准库；需要第三方包时加 `requirements.txt`，只装进仓库内 `.venv`，不要全局 pip install。
- Remotion 代码必须通过 `npm run typecheck`。发布资料新增字段要同步：`templates/listing/compliance.example.json` → `pipeline/schema/` → `pipeline/check/check.py`。
- 给用户看的文档必须是 .docx 或 .pdf（仓库内保留 .md 源）。
- 字体须有允许本项目非商业使用的许可（免费商用或仅限非商业的许可均可），并把许可证放在字体旁；不额外要求商用授权。
- 提交信息用英文。

## map-hub 口播 series (@贝壳-TV) — end-to-end runbook

执行更新（2026-10-12）：先读 `docs/maphub-execution.md`。每期渲染 cwd 是 `<ep>/work/remotion`，不切换共享模板链接；后台入口支持 auto/claude/zcode/opencode，Grok 只显式选择。IndexTTS-2.5 主用，F5 显式备用；上传入口合并共享 voice、单期覆盖与逐行设置。正式克隆音频缺段或缺有效词时间戳必须停止，Edge 与估算字幕只用于草稿。正式渲染走 `pipeline/maphub/render_episode.py`，之后仍必须通过原有审片流程。

- **Start here:** `docs/RUNBOOK-map-hub-koubo.md` (listing → POIs → script → IndexTTS-2.5 voice clone on one Kaggle T4 → Muse via Playwright → annotations →
  HeyGen via Playwright → heygen_mark → split → matting → assemble → QA, plus the user's taste rules).
- HeyGen download writes `heygen/export.mp4`. Then `python pipeline/maphub/heygen_mark.py <ep>` covers only the bottom-right mark on that original (one `generate_image` still plus a mask; the face stays sharp and the sofa stays soft). Exit 3 means save `heygen/mark/repair.png` and rerun. Split uses `heygen/export_nomark.mp4` and does not overwrite `export.mp4`.
- Code: `templates/map-hub/remotion/` (Remotion 4.0.529, comps `MapHubHeygen`, `MapHubKoubo`, `Opener`) + `pipeline/maphub/*.py`.
  Rules: `rules/map-hub/`. Example episode: `projects/listing/ep02-zidong/`.
- Always `python pipeline/maphub/stage.py projects/listing/<ep>` first: it prepares `<ep>/work/remotion`; that workspace's `public/` and `src/episode/`
  into that episode, so every generated file stays inside the episode folder (no cross-episode references).
- Only the user's own HeyGen avatar ("Cool Breeze") and cloned voice; never modify the user's raw recordings; never touch
  `.mcp.json` / `.grok/`; no commit/push unless asked.

### Trigger: `做视频 <ep>` / `make-video <ep>` (fixed workflow)
When the user gives a **房源编号** or a **新房楼盘** name (or says **做视频** for an episode that has no folder yet), the agent creates the episode. Do not ask the user to run `new_episode` or to pick the folder name or the episode number.
**`做视频` routes by series**: a 房源编号 / 新房楼盘 goes to the listing pipeline below (`projects/listing`); a 知识 / 政策 / 市场分析选题 goes to the knowledge 口播 pipeline (`projects/knowledge`, next section). The map-hub pipeline refuses `series: knowledge` episodes and vice versa.
1. Next number is `npm run episodes` → `next_release_number` (shared across listing, knowledge and interview). Folder is `epNN-<pinyin>`, for example `ep08-xihu`. Category, layout, and the listing id stay in `episode.yaml`. Do not put them in the folder. Omit `--episode` and the script takes that number.
2. A listing id is `rental`, unless the user says 二手房 (`resale`). Query the rental BeikeMicroservice detail for the community name, turn it into a pinyin slug, and run
   `python scripts/new_episode.py --category rental --slug <pinyin> --listing <id> --title <小区名>`.
   The id stays in `episode.yaml` `listing.ref` and `data/listing_ref.json`. It must not appear in the folder, `episode.json`, narration, or picture.
3. A 新房楼盘 has no listing id. Run
   `python scripts/new_episode.py --category new-home --slug <pinyin> --title <楼盘名>`.
   The name is `listing.community` in episode.yaml (no data file). Developer documents go to `sources/docs/`. Do not invent a listing id.
   Camera footage: add `--footage <dir>` (copied as-is, DJI names kept) or copy into `footage/raw/` later, then `npm run manifest -- <ep> --init` and `npm run restore -- <ep>`.
4. A knowledge or market 选题 has no listing id and does **not** go into projects/listing: run
   `scripts\new-knowledge-episode.cmd --slug <pinyin> --topic <选题>` (own numbering from ep01, default city 成都), then follow `docs/RUNBOOK-knowledge-koubo.md`.
5. Then read `episode.yaml` and follow `docs/RUNBOOK-map-hub-koubo.md` from the first stage whose `status` is not `done`. Footage rules: `docs/FOOTAGE-SPEC.md`.
Long stages run detached: `scripts\make-video.cmd <ep> [stage]` (logs in `<ep>/jobs/<stage>.log`, resumable).
Generated wavs stay in the episode; `voices/clone/` is the shared reference.

### Shared resources (do not copy per episode)
- Presenter: `assets/presenter/cool-breeze/presenter.yaml` — HeyGen avatar Cool Breeze, voice clone ref + IndexTTS-2.5 on one Kaggle T4 (seed/speed still from this profile), Muse avatar ref, matting.
  episode.yaml says `presenter: cool-breeze`; optional `presenter_override` per episode. Never edit the profile for one episode.
- Fonts + brand logos: `templates/map-hub/shared/public/{fonts,brands}` (linked into each episode by stage.py).

## knowledge 口播 series (@贝壳-TV) — 知识/政策/市场分析，独立于 map-hub

- **Start here:** `docs/RUNBOOK-knowledge-koubo.md`. Episodes live in `projects/knowledge/epNN-<slug>` with their **own numbering from ep01**
  (independent of map-hub). No listing id, no map/POI steps; the episode is a 选题 with facts sourced in `script/research.md`.
- New episode (agent runs it when the user gives a 选题): `scripts\new-knowledge-episode.cmd --slug <pinyin> --topic <选题> [--title 片名] [--city 成都]`.
  Runbook: `docs/RUNBOOK-knowledge-koubo.md`. Example episode: `projects/knowledge/ep01-intro/`.
- Pipeline: `pipeline/knowledge/` (episode loader + timeline + `make_video.py` orchestrator with steps voice/heygen-plan/matte/compose/render).
  Entry: `scripts\make-knowledge-video.cmd <ep> [step] [--check] [--draft]`. Always `--check` first; it never spends credits.
- Shared with map-hub (imported, never duplicated): presenter profile, `voices/clone/`, shared fonts/brands, `scripts/voice/clone_tts.py`
  (flova MiniMax passage chain), `pipeline/maphub/heygen_plan.py`, `workspace.py` (series-aware staging), matting scripts.
- Remotion: `templates/knowledge/remotion/` comp `KnowledgeKoubo` (1440x1080 @30fps): on-cam HeyGen segments alternate with voiceover
  b-roll segments (flova stills backup first, then Muse video; 贝壳找房 app UI is always real screenshots), data cards, process animation,
  brand wall, top-right 视频号 @贝壳-TV / 抖音 @贝壳TV. HeyGen look is "Professional in suit on sofa", on-cam segments only.
- Script rules enforced by the loader: total 80-90s, on-cam合计 ≤ 55s (HeyGen free one-minute cap), never use —— or -- in spoken text,
  no 最/第一/唯一. Numbers on screen must trace back to `script/research.md`.
