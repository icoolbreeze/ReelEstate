# HeyGen 数字人生成操作说明（Cool Breeze，免费版）

验证日期：2026-10-21（ep02-zidong）。由 box 浏览器 computerUse 完成，HeyGen 已登录。

## 规则
- 必须使用 Cool Breeze 的保存形象 "Professional in suit on sofa"，禁止默认/其他形象。
- 免费版：时长 < 60 s，720p（1080p 付费），成片右下角有 HeyGen 水印。
- 音频用上传方式（不用 TTS）：`projects/listing/<EP>/heygen/heygen_audio_*.wav`，先 CopyToBox 到 box。

## 步骤
1. 打开 `https://app.heygen.com/avatar`（会跳到 `/avatar/avatar-shots`，"What should your avatar say?" 编辑页；默认是公共形象 Leslie、Avatar IV、竖屏）。
2. 悬停头像缩略图 → 点 "Switch look"（弹窗停在 Public Avatars → Leslie）。
3. 点面包屑 "Public Avatars" → "Choose Avatar" 弹窗 → "My Avatars" 标签。
4. 点 "Cool Breeze"（7 looks）。
5. 点 "Professional in suit on sofa"（Upload 方块后的第一个）。弹窗关闭，声音显示 Cool Breeze，模型变为 Avatar V。
6. 点 "720p" 左边的画幅下拉 → 选 "Landscape"。
7. 脚本框点 "upload/record" → 切到 "Upload Audio" 标签（默认先开录音，会报 No microphone found）→ 上传 wav（MP3/WAV ≤100MB，也收 m4a/ogg）。
8. 约 10 s 后出现 "Confirm Audio"，核对文件名与时长 → Voice Mirroring 保持关闭 → "Add audio"。
9. 分辨率保持 720p；Motion、Captions、音乐都不动。
10. 点工具栏右侧圆形箭头 "Generate"，提示 "Your video is generating"，Recent Creations 出现进度。
11. 约 4 分钟完成（99% 会卡约 1 分钟，正常）。
12. Recent Creations 顶部方块 → 底部下载图标 → 弹窗（Video/Captions/Audio）→ 点 "Download"。
13. 文件存到 `/home/box/Downloads/Avatar Video_720p.mp4`，改名复制到 `episodes/<EP>/heygen/heygen_<ver>.mp4`，再 CopyFromBox 到 PC 的 `projects/listing/<EP>/heygen/`。

## 坑
- 截图常落后 1–2 个动作，以页面文字为准。
- "Choose look" 按钮悬停才出现，普通点击会被 div 拦截，用强制点击或坐标点击。
- 编辑页小缩略图看不清背景，形象要在成片缩略图里（沙发场景）再确认一次。
- 下载图标先开弹窗，要再点 "Download"。
- 拿到成片后跑抠像和 `check_matte`，然后去掉 `--presenter-placeholder` 正式渲染。
