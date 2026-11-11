# templates/knowledge — @贝壳-TV 知识口播系列模板

`remotion/` 是 `KnowledgeKoubo` 合成（1440×1080 @30fps）的模板，由 `pipeline/maphub/workspace.py stage_episode`
拷进 `<ep>/work/remotion`；数据全部来自 `src/episode/*.json`（由 `pipeline/knowledge/timeline.py` 生成）。

## 硬规则

1. **画面永不出现内部文件名 / 路径 / 源文件标签**（如 `research.md`、`broll/…`、`S01`、`.json`、素材 ref）。
   观众可见的文字只能是面向观众的内容；数据溯源写在 `<ep>/script/research.md`，不写上屏。
   `brands.json sourceMark.label`、占位卡、角标、字幕都一样受限。
2. 口播/字幕/画面永远不用 `——` 或 `--`；不出现电话/微信/二维码/网址/站外 logo。
3. 手机屏幕只用真实截图（`<ep>/broll/screens/`），放进 `PhoneMockup`；**绝不**用 AI 生成的手机/App 画面。
4. 动效组件在 `remotion/src/components/MotionV2.tsx`（PhoneMockup / CounterCards / PinMap / BrandWall /
   KwChips / BigFact）+ `ScanAnnotate.tsx`（scanline-annotate-focus）。新动效优先加进 MotionV2，不要堆静态海报 + 慢推。
5. 数字必须能回查到 `<ep>/script/research.md`；CounterCards / BigFact 的数值同此约束。
