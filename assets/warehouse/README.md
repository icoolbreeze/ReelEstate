# assets/warehouse — 本地素材库（占位/演示素材）

- **媒体文件不提交 git**（见 `.gitignore`），只提交本说明和 `SOURCES.json`。
- `assets:import` 阶段把这里的素材复制进项目的 `raw/stock/`、`raw/presenter.mp4`、`audio/`，并写入项目 `assets/manifest.json`（来源、许可、水印、AI 标记、sha1）。
- 这些是**演示占位素材**：室内/外景是图库照片，**不是房源实拍**。正式视频必须换成业主授权的实拍，或在画面上标注“示意图”。

| 目录 | 内容 | 许可 |
|---|---|---|
| interiors/ exteriors/ covers/ | Unsplash 作者照片，经 Wikimedia Commons 收录 | CC0 |
| presenter/presenter.mp4 | Pexels #6963825 “Woman Recording her Self”，cottonbro studio；裁 4:3、正放+倒放循环 | Pexels License（可商用，禁止原样转售；条款待核实） |
| audio/bgm.mp3 | Mixkit “Sweet September” #282 | Mixkit Free License（条款待核实） |
| audio/whoosh.mp3 / click.mp3 | Mixkit #166 / #2582 | Mixkit Free License |

逐项见 `SOURCES.json`。新增素材时同时更新 `pipeline/stages/assets.py` 的 `STOCK_CATALOG`。
