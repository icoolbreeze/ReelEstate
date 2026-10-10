# pipeline（全部可在 Windows / macOS / Linux 跑，路径相对本仓库）

| 脚本 | 作用 | 输入 → 输出 |
|---|---|---|
| `coords.py` | GCJ-02⇄WGS-84（迭代反解，<1 m）、Web 墨卡托平面投影 `Plane`、haversine | 库；`python coords.py` 自检 |
| `amap_fetch.py` | 按 `episode.json.poiQueries` 用 map-tools/map.py 查 POI、取步行/驾车路线距离和折线，投影到平面 | `episode.json` → `pois.json`、`raw/route_*.json` |
| `build_vo.py` | edge-tts 逐行合成（带字词时间），算出每行帧号、字幕块帧号、点击帧；混音（TTS + BGM 闪避 + 点击/转场音效 + 开场音效），响度 −16 LUFS | `script.json` → `proj/src/episode/timeline.json`、`proj/public/episode/{vo/*.mp3,mix.wav}`、`script_timed.md` |
| `make_muse_batches.py` | 镜头表转 Muse 分批消息 + manifest | `shots.json` → `muse/batchN.txt`、`muse/manifest.json` |
| `track_annotations.py` | `grid`：素材首帧加 10% 网格方便定框；`track`：从种子框双向跟踪（flow 默认 / vit / csrt），平滑，写关键帧 | `footage/<ID>.mp4` + `annotations/seeds/<ID>.json` → `annotations/<ID>.json`（+ `_preview.mp4`） |
| `sync_assets.py` | 素材、标注、episode/pois 同步进 Remotion；缺素材时自动用占位（静图慢推 / 主持人旧片段 / 待生成卡） | → `proj/public/footage/`、`proj/src/episode/{footage,annotations,episode,pois}.json` |
| `basemap/amap_vector.py` | 高德无标注瓦片矢量化（道路骨架、水体、绿地、楼块） | → `vector.json` |
| `basemap/build_map_A.py` | 按 Canva 色板 A 画插画底图 | `vector.json` → `base_A.png` |
| `satellite/*` | Google z18 卫星瓦片（WGS-84）→ 换算到 GCJ 平面 → 调色 | → `sat_z18_corr.png` 等 |
| `flova/make_src.py` → `flova/flova_edit.js`（用户电脑） → `flova/align.py` → `flova/build_base_v6b.py` | flova gpt-image-2.5 一次编辑（图1 底图被编辑、图2 卫星仅参考）→ 结构掩膜 ECC 对齐 → 外围丰富化 + 金字塔融合 | → `base_flovaSat3Db.png`（细节和实测残差见 `flova/README.md`） |

跟踪器选择：Muse 素材是慢推/慢移的静态场景，`flow`（LK 光流 + RANSAC 相似变换）在合成慢推测试里误差 <0.002（归一化），TrackerVit 把沙发框放大了约 25%，所以默认 `flow`。`models/object_tracking_vittrack_2023sep.onnx` 来自 opencv_zoo（https://github.com/opencv/opencv_zoo/tree/main/models/object_tracking_vittrack）。
