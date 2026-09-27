# 新建一个房源项目

## 1. 创建

```powershell
npm run new -- rental lvcheng-2b1l                 # → projects/rental/<今天>-lvcheng-2b1l
npm run new -- resale binjiang-3b2l --date 2026-10-03
npm run new -- new-home xihu-yuefu --title "西湖悦府 新房讲解"
```

命名：`<YYYY-MM-DD>-<拼音/英文短名>`，只用小写字母、数字、连字符。建议格式 `小区拼音-户型`，如 `lvcheng-2b1l`（2 bedroom 1 living）。中文名写进 `project.json`。

## 2. 目录

```
projects/rental/2026-10-03-lvcheng-2b1l/
  project.json   # 房源信息 + 口播分段（来自 templates/rental/）
  raw/           # 口播视频、实拍、户型图原图
  canva/         # Canva 导出卡片
  audio/         # TTS 输出（seg_*.wav, segments.json）
  consent/       # 业主委托书、出镜/声音授权书
  output/        # 渲染成片、单帧预览
```

整个项目目录被 gitignore（私有素材）。备份请用网盘/NAS，不要 `git add -f`。

## 3. 填写 project.json

字段说明见 `templates/README.md`。重点：
1. 替换所有 `待填`；
2. 面积写口径（`建筑面积`/`套内建筑面积`），价格写有效期；
3. `drawbacks` 至少一条；
4. 出镜人为视频号认证本人后，`agent.certified_on_camera` 改为 `true`；
5. 分类专项：二手房 → 核验编码 + `consent/` 委托书；新房 → 开发商全称 + 预售证号 + 效果图标注；租赁 → 月租金 + 押付方式。

口播分段示例：

```json
{"id": "s02", "text": "建筑面积八十九平，两室一厅。", "presenter": "pip-right",
 "presenter_clip": "raw/talk-01.mp4", "clip_start": 12.5,
 "card": {"title": "房源信息", "lines": ["2室1厅1卫", "建筑面积 89㎡"]}}
```

## 4. 检查与渲染

```powershell
npm run check  -- projects/rental/2026-10-03-lvcheng-2b1l
npm run still  -- projects/rental/2026-10-03-lvcheng-2b1l --frame 60
npm run render -- projects/rental/2026-10-03-lvcheng-2b1l --ratio 9x16
```

渲染时项目目录作为 Remotion 的 public 目录，`presenter_clip` 等路径相对项目目录。
