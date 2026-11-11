# 素材目录与命名（房源讲解：rental / resale / new-home）

2026-10-30 起只保留下面这一套目录。旧的 `projects/map-hub/` 联接、`projects/<category>/<date>-<slug>/`（project.json）布局、
`footage/<ID>.mp4` 放在 footage 根目录、`footage/listing/`、期根目录 `raw/` 都已退役。

## 一期的目录

```
projects/listing/epNN-<slug>/
├─ episode.yaml  episode.json  compliance.json(.draft)  README.md
├─ data/                     timeline / footage / pois / listing_ref（rental、resale）等 JSON；没有 project.json
├─ sources/
│  ├─ amap/                  高德路线原始返回 route_*.json（amap_fetch 写）
│  └─ docs/                  新房开发商资料原件（楼书 docx/pdf、价格表），只作核对依据
├─ footage/
│  ├─ raw/                   原片，只读。保留相机原名（DJI_*_D.MP4、手机名、房间_序号.mp4 都可以）
│  ├─ raw_manifest.json      原片 → 房间 / 镜头 id / 入出点（不写进 raw/）
│  ├─ selects_dlogm/         从 raw 无损截取的 D-Log M 片段（restore --select）
│  ├─ restored/
│  │  ├─ master/             10-bit ProRes 母版 <名>_r709.mov（达芬奇精调、抠像）
│  │  ├─ proxy/              8-bit H.264 代理 <名>_r709.mp4（Remotion 渲染）
│  │  └─ color_report.json
│  ├─ shots/<ID>.mp4         模板镜头（Muse 输出，或按 manifest 入出点从代理截出的 Rec.709 片段）
│  ├─ heygen/                HeyGen 切段 HG*.mp4、HG00_alpha.webm
│  ├─ matte/                 抠像结果（matte_local 默认写这里）
│  └─ assets/                本期采用的静态素材
│     ├─ rental / resale：floorplan/ photos/ map/
│     └─ new-home：brochure/ renderings/ sandtable/ map/
├─ heygen/                   HeyGen 计划与原始导出（segments.json、export*.mp4、mark/）
├─ voice/  annotations/  consent/
├─ public/                   由 stage / sync 生成，work/remotion/public 链接到这里
├─ work/                     临时工作区（work/remotion 由 stage 生成，可整体重建）
└─ out/drafts/  out/release/
```

- `npm run new` 只建 `footage/raw`、`data`、`consent`、本类别的 `footage/assets/*`（新房另加 `sources/docs`），以及空的 `footage/raw_manifest.json`。其余目录由第一次写入它的工具创建，空目录不预建。
- 共享素材（字体、品牌、LUT、数字人）不复制进期内。素材不放进 `templates/` 或其他期。
- 还没归到某一期的原始资料放 `projects/listing/_sources/<ascii-slug>/`（例如 `_sources/wuhou-xipai-yufu/`），建期后复制进该期 `sources/docs/` 或 `footage/raw/`。

## 原片命名与 raw_manifest.json

- `footage/raw/` 只读：不改名、不覆写、不删除。从 SD 卡或 U 盘只复制。相机原名保留，DJI `.LRF` 代理忽略。
- 房间和镜头的对应写在 `footage/raw_manifest.json`：

```json
{"version": 1, "episode": "ep03-bangtai-cangjin",
 "clips": [{"file": "DJI_..._0271_D.MP4", "room": "样板间客厅", "shot": "LR1", "in": 2.0, "out": 8.5,
            "use": "auto", "duration_s": 42.1, "note": ""}]}
```

- `npm run manifest -- <ep> --init`：把还没登记的原片补进清单（`房间_序号` 命名的自动填 room），已有行不动；`npm run manifest -- <ep>` 只校验。check 也会校验：清单里的文件必须在 raw 里、`use` 只能是 auto / must / skip、同一个 shot 不能对应两段原片；raw 里没登记的片段是警告。
- 房间名建议：客厅、主卧、次卧、卧室、书房、厨房、卫生间、餐厅、阳台、玄关、外立面、小区、大堂、周边；新房另有 样板间、会所、售楼部、沙盘、园林、区位。
- 拍摄要求：横屏，≥ 1080p，每段 4–15 秒，稳定（云台或慢摇），不拍人脸和车牌。

## 镜头 id

| room | clip IDs | map card |
|---|---|---|
| 客厅 / 样板间客厅 | LR1, LR2 | room_living |
| 主卧/卧室/次卧 | BR1, BR2 | room_bed |
| 厨房/卫生间 | KB1, KB2 | room_kb |
| 小区/外立面/大堂/会所/园林 | ENV1–ENV3 | env |
| 周边 | NB1–NB3, MET1 | POI cut-aways |

`sync_assets` 取镜头的顺序：`footage/shots/<ID>.mp4` → `footage/raw|selects_dlogm/<ID>.*` → `raw_manifest.json` 里 `shot=<ID>` 的原片。
后两种自动换成还原代理；manifest 写了 `in/out` 时，从代理重新编码截出 `footage/shots/<ID>.mp4`（逐帧准确，Rec.709）。
没有实拍的房间由 Muse 生成（`episode.yaml` 的 `footage.muse: auto`），通用 Muse 画面口播说明“画面仅作示意”。新房默认 `muse: none`，只用实拍和开发商资料。

## DJI Osmo Pocket 3 调色（D-Log M）

拍摄默认用 D-Log M。LUT 放在公共资源区 `assets/luts/pocket3/`，各期不要复制：

- `restore/DJI OSMO Pocket 3 D-Log M to Rec.709 V1.cube`：还原 LUT。每段 D-Log M 素材必须先过它。
- `style/`：Spring / Summer / Autumn / Winter Pro 四个风格 LUT（Rec.709 to Color Grading）。只能叠在还原之后，不能直接套 D-Log M 原片。

顺序固定：原片（D-Log M）→ 还原 LUT → 风格 LUT（可选）→ 后续抠像、渲染。普通色彩模式拍的素材不用还原 LUT。

本期用了哪个风格 LUT（或不用），写在该期 `episode.yaml`。原片保留在 `footage/raw/` 不改，调色后的文件另存。

### 自动识别与自动还原

导入素材后直接运行，不用手动判断：

```powershell
npm run restore -- --scan D:\DCIM\DJI_001                       # 只读扫描任意文件夹（如 SD 卡），什么都不写
npm run restore -- projects/listing/<episode> --dry-run        # 只识别，不写文件
npm run restore -- projects/listing/<episode>                  # 识别 + 还原：10-bit ProRes 母版 + H.264 代理
npm run restore -- projects/listing/<episode> --style Spring   # 另出一份 还原+风格 版本
npm run restore -- projects/listing/<episode> --gate           # 只跑色彩门槛（check 也会跑）
npm run restore -- projects/listing/<episode> --select DJI_xxx_D.MP4 --in 3.2 --out 9.5   # 无损截取到 selects_dlogm 并还原
```

知识口播和会客厅把路径换成 `projects/knowledge/<episode>`、`projects/interview/<episode>`，规则相同。

**素材目录**

- `footage/raw/`：原片，只读，永不修改。DJI 的 `.LRF` 低清代理文件忽略。从 SD 卡或 U 盘只复制，不移动、不删除卡上的文件。
- `footage/selects_dlogm/`：约定目录。放进来的片段一律按 D-Log M 处理，不再识别。HLG/PQ 片段放进来会报错。
- `--select <raw 片段> --in <秒> --out <秒>` 用流拷贝（不重新编码、无损）把 raw 里的 D-Log M 片段截一段放进 `selects_dlogm/`，名字是 `<名>_<入点ms>-<出点ms>.MP4`，随后自动还原。流拷贝只能从关键帧切，实际起点是入点或它之前最近的关键帧。
- `footage/restored/master/`（ProRes）、`footage/restored/proxy/`（H.264）和 `footage/restored/color_report.json`。selects 的输出名前加 `selects__`。

**输出（默认）**

- `master/<名>_r709.mov`：ProRes 422 HQ，10-bit 4:2:2（`yuv422p10le`），PCM 音频。写 BT.709 标签和“已还原”标记，供达芬奇（免费版）精调、抠像。LUT 在 16-bit RGB 里计算，中间不降到 8-bit。
- `proxy/<名>_r709.mp4`：8-bit H.264 代理，AAC 音频，有 NVIDIA 显卡用 nvenc，否则 x264 crf 16。Remotion/Chrome 不能解码 ProRes，渲染用它。
- 体积和速度（ep03 实测，126 段共 13.8 分钟）：ProRes 32.3 GB（约 39 MB/秒，约 2.3 GB/分钟），代理 1.6 GB（约 2 MB/秒）。母版加代理整批耗时约 10.5 分钟，约 1.3 倍实时。开工前先确认磁盘空间。`--no-proxy` 不出代理，但 check 会失败，直到代理生成。`--encoder x264|nvenc|auto` 只出 H.264。
- 加 `--style` 另出 `<名>_r709_<Style>.mov/.mp4`，一次完成 还原→风格，不二次压缩。不写 `--style` 时读 `episode.yaml` 的 `color: {style: Spring}`，没有就只还原。
- 输出已存在且比原片和 LUT 新就跳过，中断后重跑会接着做；`--force` 强制重做。

**后续环节自动用还原版**（`restored_for()` in `color_restore.py`）

- 房源 `sync_assets`：镜头 `footage/shots/<ID>.mp4` 不存在时，找 `footage/raw/`、`footage/selects_dlogm/` 里同名 `<ID>.*` 的片段，再找 `raw_manifest.json` 里 `shot=<ID>` 的原片。D-Log M 片段一律换成 H.264 代理再进 Remotion。
- 会客厅：渲染切片用代理；抠像用 ProRes 母版（`media_sources.json` 仍写 raw 路径，换成还原版是自动的）。
- `scripts/matting/matte_local.py`：输入是期内 raw 或 selects 的 D-Log M 片段时，自动改用 ProRes 母版；不写 `--out` 时输出到本期 `footage/matte/`。
- 未还原的 D-Log M 被引用时直接报错，不会把灰片带进成片。

**check 门槛**（三条线的 `npm run check` 都跑）

- 报错：D-Log M 片段（raw 按报告或元数据判定，selects 一律算）缺少或过期的 ProRes 母版或 H.264 代理。
- 报错：10-bit 片段还没识别过（没跑 restore）。
- 报错：`public/`、`footage/shots/`、`footage/` 根目录、`broll/` 里有未还原的 D-Log M 进了渲染。
- 警告：colour unknown（没还原，需人看）、HLG/PQ。
- `color_report.json` 记录每段原片的大小和修改时间。原片变了就按未识别处理，要重新跑 restore。

**unknown 的处理**

先人工确认，再用 `--assume dlogm --only <名> [<名> ...]`。`--assume` 必须配合 `--only` 逐个点名，而且永远不会作用于 HLG/PQ 片段。

判定规则（`pipeline/common/color_restore.py`）。2026-10-28 用 SD 卡上 129 段真实 Pocket 3 素材（全部 1080p 29.97）和 ep02 的 26 段手机素材校准；其他分辨率、帧率或固件仍需复核：

1. 文件带本工具的还原标记，或名字以 `_r709` 结尾：已还原，跳过。
2. 色彩传递为 HLG/PQ（`arib-std-b67` / `smpte2084`）：HLG 素材，不是 D-Log M，不套还原 LUT，标 unknown。
3. 8-bit：判为普通色彩（Pocket 3 的 D-Log M 只能录 10-bit HEVC）。
4. 10-bit 的 DJI 文件：读 `DJI dbgi` 数据流里的传感器模板名。
   - 以 `_10BIT` 结尾（如 `TPLG_IMX989_VIDEO_1080P_2997_HDR_10BIT`）判 D-Log M。
   - 模板是 `..._HDR` 或 `..._LOWLIGHT`（不带 `_10BIT`）的标 unknown。卡上有 11 段，黑位压到 4–15（低于合法黑 16），饱和度偏高，看起来像普通模式。
5. 普通元数据区分不了 D-Log M：所有片段都是 HEVC Main 10、`yuv420p10le`、标 BT.709，`encoder=DJI OsmoPocket3`。
6. 没有 DJI 模板的 10-bit 素材看画面：均匀抽 5 帧，用 ffmpeg signalstats（8-bit 限制范围刻度）计算。必须同时满足最暗像素 ≥ 17（黑抬起）和平均饱和度中位数 ≤ 8，才判 D-Log M，否则 unknown。
7. 实测数据：
   - 真实 D-Log M：最暗像素中位数 24，饱和度 0.8–12.9（中位数 4.5）。最亮可到 255，所以高光和亮度跨度不参与判断。
   - 手机 Rec.709：最暗像素 14–32，饱和度 4–18。
