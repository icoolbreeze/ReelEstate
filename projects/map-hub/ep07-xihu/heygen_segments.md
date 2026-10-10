# HeyGen segments — ep07-xihu

ONE landscape 16:9 video, 720p, avatar **Cool Breeze**, audio = upload `heygen/heygen_audio.wav` (lip-sync to our audio; do not type the script).
Total length **42.22 s** (speech 36.97 s + 0.5s pauses) — free-plan limit 60 s, our budget 55 s.

Framing: keep the face near the horizontal centre — Remotion centre-crops 16:9 → 4:3 (keeps the middle 75 % of the width).

| # | seg | line | layout | text | speech (s in export) | dur | cut in → out | cut dur |
|---|---|---|---|---|---|---|---|---|
| 1 | HG00 | HOOK | A (hook, before opener) | 月租，四千八！西湖文化广场，两室一厅。整面落地窗，人字拼地板——离地铁站，只有五百七十一米。 | 0.25–7.87 | 7.62 | 0.00 → 8.12 | 8.12 |
| 2 | HG01 | L04 | PIP | 这张地图，就是目录：房间、小区、周边——点到哪，讲到哪！ | 8.37–12.78 | 4.41 | 8.12 → 13.03 | 4.91 |
| 3 | HG02 | L11 | PIP | 好，回到地图——下楼，看看小区！ | 13.28–15.67 | 2.39 | 13.03 → 15.92 | 2.89 |
| 4 | HG04 | L16 | PIP | 地铁，西湖文化广场站。步行，五百七十一米。一号线、三号线、十九号线——都在这一站！ | 16.17–22.80 | 6.63 | 15.92 → 23.05 | 7.13 |
| 5 | HG05 | L17 | PIP | 上学：杭州长江实验小学，步行三百三十六米；朝晖中学，步行约一点六公里。 | 23.30–29.01 | 5.71 | 23.05 → 29.26 | 6.21 |
| 6 | HG06 | L20 | PIP | 看病：浙江省人民医院朝晖院区，驾车，约一点九公里。 | 29.51–33.41 | 3.89 | 29.26 → 33.66 | 4.39 |
| 7 | HG08 | L23 | PIP | 想看真实在租的房源？评论区，留下你的预算，和通勤地点！ | 33.91–38.22 | 4.31 | 33.66 → 38.47 | 4.81 |
| 8 | HG09 | L24 | PIP | 我是贝壳TV——我们，下期见！ | 38.72–40.72 | 2.00 | 38.47 → 42.22 | 3.75 |

Split after download:

    python pipeline/heygen_plan.py projects/map-hub/ep07-xihu split <path/to/heygen_export.mp4>

If HeyGen's export is longer/shorter than the plan (it can add ~0.1–0.5 s at the head), set `--offset <s>` on split (positive = export starts later).
Then `python pipeline/sync_assets.py projects/map-hub/ep07-xihu` and render.
