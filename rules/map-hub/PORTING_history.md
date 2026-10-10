# 移植到 ReelEstate（C:\Users\shipi\vswp\ReelEstate，GitHub icoolbreeze/ReelEstate）

还没有推送。建议放法：

| 本目录 | 仓库内 |
|---|---|
| `proj/`（去掉 `node_modules/`、`public/footage/`、`public/episode/`） | `series/map-hub/remotion/` |
| `pipeline/`（含 `basemap/ flova/ satellite/`，`models/*.onnx` 不进 git，README 里写下载地址） | `series/map-hub/pipeline/` |
| `rules/` | `series/map-hub/rules/` |
| `docs/AGENTS_map-hub.md` | 合进根目录 `AGENTS.md`（或链接） |
| `episodes/ep07-xihu/` | `series/map-hub/episodes/ep07-xihu/`（`raw/` 可不提交） |
| `muse/`、`footage/`、`annotations/` | 每期的工作目录；素材建议走 LFS 或不进 git，只提交 `annotations/*.json`、`seeds/*.json`、`muse/*.txt|json` |
| `README.md` | `series/map-hub/README.md` |

## 移植前要做的事
1. **node_modules**：本机是从 multiplane-opener 硬链接过来的，仓库里要 `npm ci`（Remotion 4.0.529，React 19.2.3）。
2. **大文件**：`proj/public/map/base_flovaSat3Db.png`（5440×5680，约 16 MB）、`public/placeholder/*.mp4`（约 9 MB）、字体（约 77 MB）。建议 LFS；或者只提交生成脚本，底图放 release 资源。
3. **字体授权**：`public/fonts/` 里阿里妈妈数黑体、Noto Sans SC、Barlow Condensed 均为可商用字体，入库前确认 OFL/授权文件一起提交。
4. **品牌 logo**：`public/brands/` 来源见 `brands.md`；富房 logo 来自设计方公开案例图，正式发布前最好换官方文件。
5. **Windows 路径**：脚本全部用 `pathlib` / 相对路径；高德 key 从 `~/.config/map-tools/keys.json`（Windows 即 `%USERPROFILE%\.config\map-tools\keys.json`）读；map.py 位置用 `$MAP_TOOLS_PY` 覆盖（默认 `~/.agents/skills/map-tools/scripts/map.py`）；flova 用 `$FLOVA_MCP_SERVER`（默认 `~/.flova-mcp/server.js`）；shotcraft 音效目录用 `$SHOTCRAFT_DIR`（默认与本目录同级的 `video-shotcraft/`）。
6. **`--gl=angle`**：Linux 无头渲染用；Windows 本机可去掉或用 `--gl=angle` 照常。
7. **底图脚本**：`pipeline/basemap`、`pipeline/flova`、`pipeline/satellite` 是从 multiplane-opener / koubo-test 搬过来的 v6b 流程，只做了绝对路径替换（`$MAPHUB_VECTOR`、`$MAPHUB_MAPDATA`、瓦片缓存 `~/.cache/map-hub/tiles`），内部仍按 `../proj/public/map/...`、`../sat/...` 的相对目录工作，**没有在新结构下完整重跑过**。要做成"一条命令出新一期底图"，还需要把输入输出改成 `--episode` 参数（make_src → flova_edit.js → align → build_base_v6b）。
8. **opener 数据**：`proj/src/episode/listings.json`（卡片档案页）、`mapdata.json`（opener 用的步行路线和地铁）、`sat.json` 是 EP.07 的；新一期需要按 `pois.json` 生成 `mapdata.json`（字段 listing/route/route_m/pois），这一步还没有脚本，目前是从 koubo-test 复制。
9. **时长**：EP.07 草稿 94.3 s，比 60–90 s 目标长约 4 s，可删 L08 或把 L13/L14 并进 L12。

## Added for footage pass (port these too)
- `ScanAnnotate` `mediaOffset` prop; keyframe time = (startFrom + offset + frame)/30 regardless of source fps (Muse = 24 fps).
- Insert groups in `MapHubKoubo.tsx` + `build_vo.py` `insert` handling; `clipTags`; room stills in `sync_assets.py`.
- `track_annotations.py`: `pad`, hand-keyed `kf`, labelled previews. Use relative paths / pathlib only (Windows OK).

## final_v2 changes to port
- `CLICK` timing constants + `OPEN_A()` in MapHubKoubo.tsx; groups open1 = click+press+open, close1 = end+close; cursor uses seg(..., E_IO) glide + pause instead of flickT.
- `REVEAL` keyed on HUB0; POI labels always shown after reveal; metro route moved into focus-span path logic.
- Opener `drawRoute` prop; Cursor.tsx: optional name plate, press scale, stronger Ripple.
- build_vo.py CLICK_LEAD 14 and per-line `gap` values above (total stays ≤ 95 s).

## final_v3 changes to port
- `Marks` `overOpener` prop (skips listing pin + metro, which the opener draws) rendered above `<Opener>` from REVEAL.rooms to OPEN_END; edge clamp of POIs while f < OPEN_END+12 with a title-block exclusion.
- `zoomAt` now covers [click − glide − pause, close1): push-in before the click; the opening rect starts from the zoomed mark rect.
- CLICK.press 11, pushZ, cursor scale; build_vo CLICK_LEAD 20; gaps L07/L09 2.5 s.

## final_v4 changes to port
- Opener.tsx: `CAM_SETTLE`, `END_S`, `metroMark` prop. MapHubKoubo.tsx: `OPENER_LAYOUT` + `OpenerMarks` (greedy spiral collision avoidance, obstacles list, leader lines). Cursor/ripple layer moved above the segment overlay; overlay gated on `f >= OPEN_A(click)`.
- Cursor.tsx `RIPPLE = { dur 30, grow 24, r 110 }`, `z` prop (screen-constant size under zoom).

## HeyGen track to port
- pipeline/heygen_plan.py (plan / split / placeholders), build_vo --script + hook, sync_assets heygen block, HeygenCut.tsx (MapHubHeygen comp), MapHubKoubo PresenterClip / AvatarBadge / HG_PAD, ScanAnnotate cx crop. Paths relative/pathlib; ffmpeg on PATH on Windows.

## v3 to port
- HeygenCut.tsx ListingCard / Smear; MapHubKoubo END layout (panel + PresenterClip PiP); brands.json row incl. 中环 (placeholder flag); build_vo END label.

## v4 to port
- NOTES flag (episode.json onScreenNotes) gating every label in MapHubKoubo/HeygenCut/Opener (OPENER_NOTES); ClipMedia `transparent`; HookShot list-behind-avatar; pipeline/matte_avatar.py; sync_assets picks `*_alpha.webm`; 中环 logo files + brands.json row.
- PC-side work goes through grok CLI on the user's machine: `grok -p "<task>" --always-approve --cwd C:\Users\shipi\vswp\ReelEstate` (single turn; `-c` to continue a stopped run).
