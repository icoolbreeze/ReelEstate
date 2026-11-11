# 小ONE会客厅

栏目显示名是「小ONE会客厅」，技术标识是 `series: interview`。嘉宾单人出镜，小ONE在镜头外提问，保留小ONE的现场声音。不默认使用 HeyGen、TTS、声音克隆、语速加快或口型生成。

发布编号与房源、知识类共用，由 `npm run episodes` 计算。`purpose: test` 不占正式编号。不要把下一期写死。

## 新建

```powershell
npm run new -- interview <slug> --topic <主题> --title <标题> --city 成都
npm run new -- interview techtest --tech-test --topic 技术测试
```

正式期目录是 `projects/interview/epNN-<slug>/`。技术测试期是 `projects/interview/ep00-techtest/`，`purpose: test`，没有 `release_number`。不要复制已有房源期或知识期当模板。

## 目录

- `footage/raw/` 主机位，只读
- `footage/aux/` 辅助机位，只读
- `footage/proxy/` 代理，可以重做
- `audio/raw/` 小ONE、嘉宾、环境底噪，分轨，只读
- `transcript/corrected.json` 校正后的逐字转录
- `transcript/outline.json` 采访提纲，不能当成字幕
- `edit/decisions.json` 剪辑清单
- `matte/` 已选片段的抠像和报告
- `data/` 时间线、布局、资料卡
- `work/` 本期 Remotion 工作区
- `out/drafts/` 技术样片和静帧
- `out/release/` 正式成片。测试期禁止写入这里

访谈素材按机位、音轨和段落区分，不使用「客厅_1、卧室_1」这类房源命名。

## 时间

剪辑和转录只用整数毫秒。`source_in_ms` 含起点，`source_out_ms` 不含出点。帧号是 `(毫秒 × fps) // 1000`。25fps 和 30fps 保持同一段真实时长，不把 30fps 的固定帧数套到 25fps。

## 制作顺序

1. 登记并用 ffprobe 读实际分辨率、帧率和音轨。
2. 做代理，并检查音画偏移。自动结果必须同时看开头和结尾；置信度不够就停下来人工确认。不默认 atempo，不自动删掉呼吸和停顿。
3. 导入校正转录。现有 `pipeline/asr/align_voice.py` 是把成稿对齐到声音，不能把提纲套成字幕。没有校正稿就保持待导入，不编造。
4. 确认 `edit/decisions.json`。每一段都要能回到原片区间。
5. 只抠已确认的片段，并带上前后余量。同一镜头延续抠像状态；换镜头就重置。长片段分块时，后一块带预热重叠，输出时裁掉重叠，避免接缝闪一下。
6. 用校正后的话生成字幕，再按剪辑把时间映射到成片。
7. 检查，再 stage，再渲染。

`--check` 和 `npm run check` 不启动推理，不调用付费接口。缺素材时状态是未完成。需要素材却没有时，导出和抠像执行退出码是 3，不是 0。

## 常用命令

```powershell
npm run doctor
npm run episodes
npm run check -- projects/interview/ep00-techtest --draft
npm run still -- projects/interview/ep00-techtest --draft --frame 0 --ver techtest
npm run render -- projects/interview/ep00-techtest --draft --ver techtest
python -B pipeline/interview/make_video.py projects/interview/ep00-techtest --check --draft
python -B pipeline/interview/make_video.py projects/interview/ep00-techtest --step resolve
python -B pipeline/interview/new_episode.py --self-test
```

正式期把路径换成 `projects/interview/<episode>`，并去掉测试期专用的 `--draft` 之前先补齐授权和素材。测试期不加 `--draft` 会拒绝写入 `out/release`。

预览使用本期工作区，不在模板目录里改 `public`：

```powershell
npm run video:stage -- projects/interview/ep00-techtest
```

stage 之后在 `projects/interview/<episode>/work/remotion` 里打开 Remotion Studio。公共依赖在 `tools/remotion`，不要按期重装。

抠像沿用本机 MatAnyone2，不另起引擎：

```powershell
scripts\matting\matte_local.cmd projects\interview\<episode>\footage\proxy\<clip>.mp4 --out projects\interview\<episode>\matte --max-size 1080
```

显式更低分辨率才加 `--max-size 720`。显存不足时不要自动改回 720。`--no-fallback` 失败就非 0 退出。自动落到 RVM 时，报告里的 `matanyone2_passed` 是 false。首帧遮罩可以用 `--mask` 替换。椅子和桌子要在 `matting.keep_furniture` 里写成 `drop`，或写成 `keep` 并提供 `furniture_mask`。

## 画面

两种背景共用同一份嘉宾资料、字幕和剪辑清单。

- `live`：保留门店画面，再叠栏目包装和资料。
- `virtual`：抠出的人物加固定透视背景和资料屏。没有参考帧时只放可替换占位，不表示已经匹配了真实机位。
- `placeholder`：技术测试用的色块和几何图形。

嘉宾在画面右侧，视线朝左侧留白。问题卡、案例卡、资料屏、姓名条和字幕都放在左侧，不压脸和手势。栏目名是「小ONE会客厅」。颜色用系列里的暖白、木色和琥珀。

代码会检查越界、压脸和压品牌条。肤色、光线、边缘闪动和演播室真实感要人工看，脚本不能代替。

## 达芬奇免费版

主流程用 Remotion 合成。达芬奇是可选交接，不是前置条件。免费版做常规合成和调色即可。Magic Mask 不是这个流程的依赖。没有验证过免费版的无人值守脚本，不要承诺能自动操作。

```powershell
python -B pipeline/interview/make_video.py projects/interview/<episode> --step resolve
```

没有已抠片段时退出码是 3，并写出 `out/drafts/resolve/handoff.json`。计划要求：

- RGB 和遮罩同尺寸、同帧率、同帧数、同起点。
- 优先用现有 ProRes 4444（`*_rgba.mov`）。Alpha 是 straight，不是预乘。导入时选 Straight，否则边缘会黑或发白。
- 本机如果拒绝 ProRes，改用 RGB 视频加独立灰度遮罩。灰度值就是遮罩。
- 给 Remotion 用的 VP9 透明 WebM 不是达芬奇的交接格式。
- PNG 序列只生成不超过 150 帧的短片段。
- 软件没安装时，GUI 导入记为待完成，不挡住其他框架工作。

达芬奇导出的成片放回 `edit/graded/` 后，可以继续用栏目字幕、资料卡和发布包装。

## 资料

只整理已经允许使用的导出文件，不新建爬虫，也不在这条流程里自动取数。

```powershell
python -B -c "import sys; sys.path[:0]=['pipeline/interview']; import research; research.import_file(r'projects/interview/<episode>/research/allowed.json', r'projects/interview/<episode>/data/research_pack.json')"
```

每条上屏数字保留来源、采集日期和统计口径，并标明挂牌价、成交价、系统样本或经纪人观点。没有数字就不推断。内部编号、电话、微信和未允许公开的内容不会进画面。内部系统截图不直接上屏。

## 拍摄清单

现场是真实门店，不是摄影棚。当前只有一根灯棒，加上窗光、现场环境和反光板。机位是 DJI Osmo Pocket 3，固定，中近景，嘉宾大约 45 度侧向，以双眼都看得到、表情清楚、交谈自然为准。

- 机位定好后不再挪。嘉宾视线朝向留白的一侧。头顶和手势都留出余量，后期不要裁到脸和手。
- 有窗时，灯棒补脸部暗侧，窗是主光。没有窗时，灯棒作主光，从眼神方向偏上打来，反光板放在暗侧。亮度必须试拍，不能按文字里的距离直接开拍。
- 曝光和白平衡锁定。看频闪、眼镜反光和背景里的杂物、门牌、屏幕。
- 两个人分开试音。拍之前拍手，作为同步点。单独录一段环境底噪。
- 正式回答前，录大约一分钟技术测试：转头、挥手、身体前倾。
- 正式镜头前后各留几秒空镜，机位保持不动。空镜只是辅助，不假设抠像模型一定要用它。

小ONE的提问声要单独能听见。嘉宾资历、回答、案例和授权没有书面材料时就保持待填，不要补。

## 什么算做完

| 状态 | 含义 |
|---|---|
| 框架 | 能新建、识别、检查、出技术静帧和技术样片 |
| 技术样片 | 色块、几何图形、测试字幕和音轨。画面上有「技术测试」 |
| 真人验收 | 实拍、抠像、口型和门店光线都看过。在此之前都是待实拍验证 |

技术样片渲染成功不是真人演播室验收通过。

## 真实布景匹配与人物微调

`render.background_src` 指向本期背景图；有背景图时模板不再叠加占位矩形和占位说明。
`render.studio.foreground` 使用输出画布像素配置 `x/y/w/h`，保持原视频宽高比，不拉伸、不逐帧移动。
`render.studio.grade` 可选 `brightness/contrast/saturation`，默认均为1；只能在对照原片后微调，不用强磨皮或全人物发光掩盖边缘。
`render.studio.compact_cards: true` 缩小资料卡，保留更多真实空间。
`render.studio.match_status: reference_matched_preview` 仅表示按该参考帧制作过预览，不能代替门店实拍验收。

选景先匹配机位高度、人物方向、主光方向和曝光，再匹配色温、背景虚化与人物比例。
头发和深色衣服后方优先用低反差中间明度墙面，避免硬竖线、强背光和高细节。
先在浅/深底上检查头发、眼镜、手指、肩部；存在残边时才小幅处理alpha，保留原透明母版和细发丝。
禁止默认大幅侵蚀遮罩、模糊整个人物或添加轮廓光。人物下缘应自然出画或由有透视依据的前景遮挡，不能在画内水平截断。
每段透明视频按段ID和缓存键写入独立文件，禁止使用相同的 `selected_alpha.webm` 公共文件名互相覆盖。
布景仍是AI生成示意，技术样片必须保留测试标识。发布前另外确认生成素材使用条件。

`render.studio.background_blur` 为输出画布上的背景虚化半径（0–16px），仅作用于布景，不作用于人物；有虚化时背景放大2%避免画布边缘露底。
会客厅的 `check:taste` 使用 layout.json 中 face/gesture 联合区域评估主体与外围清晰度；其他类型沿用中央区域，颜色、对比度和其他检查不变。
