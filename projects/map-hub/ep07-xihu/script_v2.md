# EP.07 西湖文化广场 — script v2 (HeyGen avatar "Cool Breeze" + cloned voice)

Times are at the current TTS pace (edge-tts YunjianNeural +50%, stand-in for the cloned voice); re-run build_vo after the clone exists.
Final cut = 4.9s hook + 94.4s main = **99.3s**. On-camera speech 41.2s, HeyGen render 46.7s (≤55s budget).

onCam: **A** avatar full screen · **PIP** avatar PiP over map · **VO** voice-over only (cloned voice over opener / map / B-roll).
Wherever the avatar is on screen: 「AI数字人 · AI合成声音」 label; end card: 「出镜为 AI数字人 · 旁白为 AI合成声音 · 示例数据」.

| line | in–out (s, final cut) | dur | onCam | visual | HeyGen seg | text |
|---|---|---|---|---|---|---|
| HOOK | 0.0–4.9 | 4.30 | A | avatar full screen, step-in punch per caption, hard cut to opener | HG00 | 落地窗、人字拼地板，离地铁五百七十一米，这套两室值不值？ |
| L01 | 5.2–8.8 | 3.58 | VO | multiplane → dolly → map opener (marks land) |  | 四千八一个月，西湖文化广场能租到什么样的两室？ |
| L02 | 9.1–12.1 | 3.07 | VO | multiplane → dolly → map opener (marks land) |  | 把一套示例房源放上地图，一个点一个点看。 |
| L03 | 13.0–17.7 | 4.63 | A | avatar full screen | HG01 | 两室一厅，八十九平，月租四千八。房源信息都是示例数据。 |
| L04 | 18.0–22.1 | 4.08 | PIP | map hub + avatar PiP | HG02 | 这张地图就是目录：房间、小区、周边，点到哪讲到哪。 |
| L05 | 23.3–27.5 | 4.27 | VO | B-roll LR1 + scanline annotations（光标点击 room_living） |  | 先进客厅。整面落地窗，布艺沙发配木茶几，采光是重点。 |
| L06 | 27.7–31.0 | 3.24 | VO | B-roll LR2 + scanline annotations |  | 电视柜做成整面收纳，地面是人字拼木地板。 |
| L07 | 33.5–36.2 | 2.71 | VO | B-roll BR1 + scanline annotations（光标点击 room_bed） |  | 主卧是双人床，窗边留了一排绿植位。 |
| L08 | 36.4–38.6 | 2.26 | VO | B-roll BR2 + scanline annotations |  | 次卧可以当书房，书桌靠窗。 |
| L09 | 41.1–44.4 | 3.26 | VO | B-roll KB1 + scanline annotations（光标点击 room_kitchen） |  | 厨房一字型，灶台、油烟机、冰箱一条线； |
| L10 | 44.6–47.3 | 2.78 | VO | B-roll KB2 + scanline annotations |  | 卫生间干湿分离，淋浴在玻璃隔断里。 |
| L11 | 47.9–49.8 | 1.87 | PIP | map hub + avatar PiP | HG03 | 回到地图，看楼下。 |
| L12 | 51.0–54.2 | 3.19 | VO | B-roll ENV1 + scanline annotations（光标点击 env） |  | 小区画面是AI示意，看三样：中心绿地， |
| L13 | 54.3–56.2 | 1.87 | VO | B-roll ENV2 + scanline annotations |  | 楼间距， |
| L14 | 56.3–58.1 | 1.87 | VO | B-roll ENV3 + scanline annotations |  | 还有出入口和门禁。 |
| L15 | 58.7–61.4 | 2.69 | PIP | map hub + avatar PiP | HG04 | 再看配套，距离按高德实际路线算。 |
| L16 | 61.7–66.8 | 5.04 | PIP | map hub + avatar PiP；插入 MET1；POI metro | HG05 | 地铁西湖文化广场站，步行五百七十一米，一、三、十九号线都在这。 |
| L17 | 67.1–72.1 | 5.06 | PIP | map hub + avatar PiP；POI school1,school2 | HG06 | 杭州长江实验小学，步行三百三十六米；朝晖中学，步行约一点六公里。 |
| L18 | 73.3–76.1 | 2.76 | VO | B-roll NB1 + scanline annotations（光标点击 market）；POI market |  | 买菜去世纪联华，步行六百零七米； |
| L19 | 76.2–78.8 | 2.64 | VO | B-roll NB3 + scanline annotations；POI mall |  | 逛街去银泰，步行七百九十七米。 |
| L20 | 79.1–83.0 | 3.86 | PIP | map hub + avatar PiP；POI hospital,hospital2 | HG07 | 看病去浙江省人民医院朝晖院区，驾车约一点九公里。 |
| L21 | 84.2–87.6 | 3.41 | VO | B-roll NB2 + scanline annotations（光标点击 park）；POI park |  | 环北公园，步行五百二十八米，画面只是示意。 |
| L22 | 87.9–92.4 | 4.44 | PIP | map hub + avatar PiP；POI metro,school1,market,hospital | HG08 | 总结一下：地铁、学校、超市、医院，路线距离都在两公里内。 |
| L23 | 92.7–96.0 | 3.34 | A | avatar full screen | HG09 | 想看真实房源，评论区告诉我预算和通勤地点。 |
| L24 | 96.2–98.1 | 1.87 | A | avatar full screen | HG10 | 我是贝壳TV，下期见。 |

On-camera speech total: **41.2s**; on-screen avatar time incl. pauses ≈ HeyGen render 46.7s.
