# 标准流程

## 0. 一句话成片（推荐）

```powershell
npm run make -- "帮我做一条云栖苑两室整租的视频，4800左右，影视飓风风格"
# 缺信息时会列出问题（退出码 3）→ 问用户 → 回填后重跑同一项目：
npm run make -- --project projects/rental/<id> --answer listing.pick=c03 --answer confirm.consent.owner
```

阶段：parse → listing:fetch → listing:wall → map:fetch → assets:import → script → tts → check → render。
每个阶段幂等、可单独重跑（`npm run map:fetch -- projects/rental/<id> --force`）。
script 阶段的兜底稿只是骨架：**Agent 必须按 `rules/style/<preset>.md` 重写口播与 `shots.json`**，并保证与近期视频不同。
**地图是每条视频的必选镜头**（overview / commute / amenities）；flova 生图默认开启、积分不设限，地图底图由 Agent 用 flova 图像生成重绘（`generate_image`，gpt-image-2.5，profile kid4，original:true）：`map:fetch` 写 `map/flova_request.json`，无 `map/base_ai.png` 时退出码 3，代码再叠标签/距离，署名“示意图 / AI 生成底图 / © 高德地图”——见 AGENTS.md §3E。**视频生成默认关闭**（`flova.video_allowed=false`）：用户没有明确开启，不得调 `generate_video`，不得生成任何视频（含地图动画、装饰、转场）。
详细说明见 `docs/one-sentence-workflow.md` 与 AGENTS.md §3A–3E。下面是手工流程（仍然有效）。


```
new → 素材放入 raw/ → ASR 转写（占位）→ 写口播分段 → TTS（可选）→ check → render → 发布前自检
```

### 动效随机（curated seeded randomness）
- `effects` 阶段在 script 之前运行，按镜头用途池从 `rules/effects/catalog.json` 抽动效，写 `effects.json`；种子=项目 id，重渲染结果不变。
- 想换一组：`npm run effects -- projects/rental/<id> --reseed` 然后重新 render。约束与池说明见 `rules/effects/README.md`。
- 改写 shots.json 时不必改 effects.json：渲染按镜头 id 匹配，匹配不上就按池顺序分配。

## 1. 新建项目

```powershell
npm run new -- rental lvcheng-2b1l              # 默认加今天日期前缀
npm run new -- resale binjiang-3b2l --date 2026-10-03
```

生成 `projects/<category>/<date>-<slug>/`：`project.json`（来自 `templates/<category>/`）、`raw/`、`canva/`、`audio/`、`consent/`、`output/`。

## 2. 放素材

- `raw/`：口播视频、房源实拍、户型图原图。
- `canva/`：Canva 导出的信息卡（PNG/MP4）。
- `consent/`：业主委托书/授权书（二手房必需）、出镜人或声音本人的授权书（AI 配音/克隆时必需）。
- 这些都是私有素材，**不会被 git 提交**。

## 3. ASR 转写（占位，尚未实现）

计划：`pipeline/asr/`（本地 Whisper 类模型）把 `raw/` 口播转成带时间戳的文本，辅助写分段与字幕。目前手工完成。

## 4. 写口播分段

编辑 `project.json`：
- 把所有 `待填` 替换为真实信息（check 会拦截残留的 `待填`/`示例`）。
- `narration.segments[]`：`id`（s01…）、`text`、`presenter`（`fullscreen`/`pip-left`/`pip-right`），可选 `card`（信息卡标题/要点）、`presenter_clip`（`raw/` 下的口播片段）、`visual_label`（如“效果图”）。
- 写 `drawbacks`，写清面积口径与价格有效期。

## 5. TTS（可选）

```powershell
npm run tts -- projects/rental/<id> --voice narrator_male_30
```

输出 `audio/seg_XX.wav` 与 `audio/segments.json`，并把 `ai_voice` 设为 `true`。未编译时先跑 `scripts\build-tts.cmd`（见 `docs/tts.md`）。

## 6. 合规检查

```powershell
npm run check -- projects/rental/<id>
```

中文报告：❌ 为必须修改（退出码非 0），⚠️ 为提醒，📋 为发布时手动事项。**修文案，不改规则。**

## 7. 渲染

```powershell
npm run render -- projects/rental/<id>               # 默认 4x3
npm run render -- projects/rental/<id> --ratio 9x16
npm run still  -- projects/rental/<id> --frame 60     # 单帧预览
```

render 会先运行 check，不通过则拒绝渲染。输出 `output/<id>_<ratio>.mp4`。

## 8. 发布前自检（手动，逐条确认）

1. 房源真实在售/在租，有业主书面委托，已按当地要求核验？
2. 画面/字幕/口播/封面/标题中无电话、微信、二维码、网址、店铺名、他平台 logo（含谐音变体）？
3. 价格真实并标有效期，无“示例”占位数字？面积标明口径？
4. 无绝对化用语、升值/回报承诺、学区/落户暗示、“X分钟到”表述？
5. 规划/在建配套标注；效果图/样板间/AI 画面标“效果图/非实景”？期房写了开发商和预售证号？
6. 讲了缺点？与近期视频脚本和表现形式明显不同？只在一个账号发布？
7. **用了 AI 配音/AI 画面 → 发布时勾选 AI 标注**（抖音：高级设置 → 自主声明 → 内容由AI生成；视频号：添加标注 → 含AI生成内容），并有本人书面授权？
8. **收费推广/商单 → 显著标注“广告”**；抖音商单走星图？
9. BGM 来自平台曲库或有许可记录；字体可商用？`assets/manifest.json` 每项都有来源/许可、无水印？
9a. 地图画面有图源署名；距离写“约 N 米 · 直线距离”并有来源？AI 素材只用于装饰/转场并标“AI生成”？
9b. 列表墙里其他房源已虚化或都有委托？画面无 CRM 编号/平台水印/经纪人姓名？
10. 主要出镜人是视频号认证经纪人本人？画面无黑边、清晰，标题与内容一致？
11. 挂合规留资组件（视频号留资组件/企微获客助手；抖音线索小程序），CTA 不写“私信领资料”？

## 审美与 harmony 检查（强制）

写 `shots.json` / 渲染之前先读 `rules/taste.md`；渲染后为至少 4 个不同镜头 `npm run still -- projects/<cat>/<id> --frame <N>`，再 `npm run check -- projects/<cat>/<id> --require-taste`（或 `npm run check:taste -- projects/<cat>/<id>`）。硬失败阻断交付；每张静帧必须人工看过。详见 AGENTS.md §3D。
