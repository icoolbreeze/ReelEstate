# 风格预设：qiuzhi（秋芝式科普）

> 移植自 v4 demo（box `/workspace/remotion-realestate-v2/src/v4`、`demo-v4.json`、`v4-demo/REPORT.md`）。
> tokens：`remotion/src/styles/qiuzhi.ts`。组件与 mediastorm 共用（`remotion/src/shots/*`），外观由 tokens 决定。

## 1. 全局参数
| 项 | 值 |
|---|---|
| 响度 | −17 LUFS |
| 镜头 | 2.5–5 s，信息卡可更长；spring 弹性入场（12 帧），二级信息 +10 帧 |
| 配色 | 深紫底 `#0C0716`，强调黄 `#FFD23F`，警示橙 `#FF8A3D`，标题硬投影 `6px 6px 0 #6C3BE6` |
| 字体 | 标题阿里妈妈数黑体；正文 Noto Sans SC；英文/数字 Barlow Condensed Italic（数黑体不含 ㎡，面积写 m²） |
| 小窗 | 圆形 232 px，白色描边，左下/右下 |
| 字幕 | 50 px / 800，黑色描边 + 投影 |

## 2. 结构感
- “今天只讲三件事”式议程开场；数字滚动定价（全片只有一次冲击效果）；HEADS-UP 警示卡；“+ 关注”胶囊按钮；片尾标版。
- 贴纸/图标只用可商用来源（Lucide ISC、Fluent Emoji MIT），并记录进 `assets/manifest.json`。

## 3. 注意
- 与 mediastorm 一样遵守合规与隐私规则；不要所有视频都用同一个议程/同一组效果。
- 效果轮换交给 `effects` 阶段（`rules/effects/`，种子=项目 id，避开最近 5 条视频用过的）；需要换一组时 `--reseed`。
