# rules/motion.md: 动效手感(迪士尼 12 条动画原理,改写为讲解/房产视频版)

> 适用对象:`remotion/src/effects/*`、`remotion/src/shots/*`、`remotion/src/shared/*` 里的所有入场、强调、转场动画。**fps 固定 30**,1 帧 = 33.3 ms,0.6 s = 18 f。
> 目标:不做角色动画,只借 12 条原理里能落到"字、卡片、数字、图钉、箭头"上的部分,每条都给可量数值。没有数字的形容词(如"轻快""有弹性")不算规则。
> 与 [`taste.md`](taste.md) §7 的关系:§7 给曲线与密度上限;本文件给手感参数。两者数字冲突时**以本文件更严的为准**(本文件过冲 ≤4%、回稳 ≤8 f,比 §7.1 的 ≤12% / ≤9 f 更严;§1.A 的 8-10 档"过冲 ≤12%"同样受本文件限制)。

## 0. 术语(量法)
- **过冲(overshoot)** = (峰值 − 终值) / |终值 − 起值|,按被动画属性本身的行程算。例:位移 100 px,峰值超出终点 4 px = 4%。
- **回稳(settle)** = 从峰值到与终值差 <1% 的帧数。
- **主动作** = 该元素的主入场/主强调位移或缩放;**次动作** = 图标、下划线、角标等附属动画。
- 缓动名称以 `remotion/src/effects/kit.ts` 的 `ease` 为准:`outCubic`、`outQuart`、`outExpo`、`inOutCubic`、`outBack(t, s)`、`linear`。

## 1. 十二条原理的取舍

### 1.1 保留并落成帧值

| 原理 | 规则(@30 fps) |
|---|---|
| **慢进慢出 Slow in / slow out** | 入场位移/缩放一律 `outCubic` 或 `outExpo`(长行程、价格冲击用 `outExpo`,普通卡片用 `outCubic`)。**入场不得用 `linear`。** `linear` 只允许:①持续性漂移(整段 ≤10 px 或 ≤3% 缩放,见 taste §7.1"never ends at zero velocity");②扫描/擦除类(scan line、clock-wipe);③仅透明度的淡入 ≤6 f。出场优先硬切;用缓动时 `inCubic` 且时长 ≤ 入场。 |
| **预备 Anticipation** | 价格/数字卡在主动作前放 **3-5 f** 的预备:静止停顿,或反向小位移(≤6 px 或缩放 0.97)。预备期间内容不可读性变差(文字不得先移出安全区)。其他元素不加预备。 |
| **跟随与重叠 Follow-through / overlapping** | 逐字/逐行入场的错开(stagger)**2-4 f**/单位;同一帧移动的单位 ≤3(与 taste §7.3 的 ≤5 animators 一起算)。主体停下后允许过冲 **≤4%**,**≤8 f 回稳**,震荡 **≤2 个来回**。`outBack` 的 s 取 **≤1.0**(实测过冲 3.7%;s=1.2 为 5.3%,超标;默认 1.70158 为 10%,超标)。弹簧:`damping ≥ 2·0.72·√(stiffness·mass)`(阻尼比 ≥0.72 ⇒ 过冲 ≤4%),如 stiffness 170 / mass 0.7 时 damping ≥ 15.7。 |
| **次动作 Secondary action** | 小图标、下划线、角标、光标相对主动作**滞后 3-6 f**,幅度 **≤ 主动作的 30%**(位移/缩放均按行程比)。同一时刻次动作 ≤2 个。 |
| **节奏 Timing** | 微动作 **5-8 f**(淡入、chip、角标);标准 **12-18 f**(卡片、标题、数字落定);强调 **18-24 f**,且关键数字(价格、面积、总价、租金)落定后**静止保持 ≥0.6 s = 18 f**。8<时长<12 f 落在档位之间,取 8 或 12。落定后的保持帧内允许 §1.1 所列的缓慢漂移。 |
| **夸张 Exaggeration** | 只用于**价格翻牌/价格冲击**与**被强调词**:峰值缩放 **≤1.12**。数据数字(面积、距离)的落定脉冲 **≤1.04**。每条片子 1 个主夸张点;关键词弹出沿用 taste §7.5 的 ≤3 次。其余元素缩放在 [0.88, 1.12] 内。 |

### 1.2 限用

| 原理 | 规则 |
|---|---|
| **挤压与拉伸 Squash & stretch** | 只用于**贴纸、图钉、价签**。幅度 **≤8%**(沿运动方向压扁/拉长,垂直方向反向补偿,sx·sy ≈ 1)。**房源照片、视频、文字禁用。** |
| **弧线 Arcs** | 只用于**指针、箭头、图钉**的位移(二次贝塞尔,弧高 ≤ 直线距离的 15%)。卡片、标题、数字走直线。 |
| **弹跳** | **不超过 2 个来回**;**房源照片、合规文字(免责声明、数据来源、备案/许可号)不得弹跳、不得带过冲**。 |

### 1.3 不适用(及原因)

| 原理 | 原因 |
|---|---|
| **立体造型 Solid drawing** | 针对角色体积与透视绘制;本项目元素是平面版式与真实照片,没有需要"画准"的形体。形体一致性由 taste §5 的图层与透视规则管。 |
| **吸引力 Appeal / 逐帧直接绘制与关键姿势 Pose-to-pose** | 针对角色表演与手绘流程;这里全部由代码按帧插值(Remotion),没有角色,也没有手绘关键帧。 |
| **舞台调度 Staging(叙事)** | 叙事式镜头调度由分镜(`shots.json`)与 taste §0 / §5(一个画面一个主角、安全区)负责,动效层不重复定义。 |

## 2. 19 个特效 × 原理 × 参数上限

来源:`rules/effects/catalog.json`(19 条,`transition` 池目前 0 条;`transitions.tsx` 里的 clock-wipe / color-block-step-wipe 未登记进 catalog)。原理简写:**缓**=慢进慢出,**预**=预备,**跟**=跟随/重叠,**次**=次动作,**时**=节奏,**夸**=夸张,**挤**=挤压拉伸,**弧**=弧线。"时长下限"= 最后一个元素落定后保持 ≥18 f 所需的最短 `duration_frames`(catalog 现值见括号)。

| 池 | id | 适用 | 参数上限 |
|---|---|---|---|
| opener | `blur-slide` | 缓 跟 次 时 | 逐字 stagger 4 f(字数多时缩到 2-3 f,总错开 ≤24 f);位移 ≤40 px;blur 10→0 与位移同步;过冲 0%;副标题作为一个单位滞后主标题 ≥3 f |
| opener | `lead-word-zoom` | 缓 夸 时 | 首词起始缩放 ≤1.12 → 1(现 1.8 超限,见 §4);不得再叠"蠕动"放大 >3%;其余字入场 12-18 f;过冲 0% |
| opener | `brand-frame` | 缓 次 时 | 边框生长 outExpo 12-18 f;颜色翻转 ≤4 f;标题 chip 滞后边框 ≥3 f;过冲 0% |
| chapter_title | `marker-underline` | 缓 次 时 | 标题 outCubic 18-24 f;下划线滞后标题 3-6 f,擦出 ≤10 f,线宽变化 ≤30%;过冲 0% |
| chapter_title | `brace-expand` | 缓 跟 时 | 括号张开 12-18 f;`outBack` s ≤1.0(过冲 ≤4%);回稳 ≤8 f;文字在括号内,不随括号弹 |
| data_number | `odometer-roll` | 缓 预 跟 时 夸 | 起转前 3-5 f 预备;每位锁定错开 4-6 f(>4 f 时总长 ≤30 f);锁定过冲 ≤4% 行程(现 0.5 行,需核对);落定脉冲 ≤1.04、≤8 f;**时长下限 = 40 + 6×位数 f**(4 位 = 64,catalog 下限 60) |
| data_number | `count-up` | 缓 预 时 夸 | `outQuart` 计数 24-36 f;落定脉冲 ≤1.04、≤8 f(现 1.06);下划线滞后数字 3-6 f;**时长下限 58 f**(catalog 下限 36,数字在 f40 才到目标) |
| comparison | `before-after-slider` | 缓 次 时 | 快扫 outCubic ≤8 f,慢扫 inOutCubic;分隔线与把手同速,把手图标滞后 ≤3 f;过冲 0%;照片不缩放不弹跳 |
| comparison | `dual-stat` | 缓 跟 时 | 两卡 stagger 2-4 f(现 5 f);入场 12-18 f;位移 ≤40 px;过冲 0%;数字保持 ≥18 f |
| price | `price-odometer` | 缓 预 跟 时 夸 | 同 `odometer-roll`;价格可用夸张,峰值缩放 ≤1.12;**时长下限 = 38 + 6×位数 f**(4 位 = 62,catalog 下限 60;7 位 = 80) |
| price | `price-pop` | 缓 预 时 夸 挤 | 起始缩放改为 ≤1.12 → 1,outExpo 12-18 f(现 3.2 超限);前置预备 3-5 f;环/光圈滞后 3-6 f、幅度 ≤30%;价签外壳可挤压 ≤8%,数字文字不挤压;**时长下限 38 f**(catalog 下限 30) |
| floorplan | `scan-bracket` | 缓 跟 次 时 | 四角同组同步;入场 ≤8 f;`outBack` s ≤1.0(现 1.2);扫描线线性匀速为许可的扫描类 linear;往返 ≤3 次 |
| floorplan | `scanline-focus` | 缓 跟 次 时 | 扫描线线性匀速(许可);聚焦框起始缩放 ≤1.12 → 1(现 1.75);`outBack` s ≤1.0(现 1.2);标签 chip 滞后框 ≥8 f(现 8 f) |
| location_map | `pin-callout` | 缓 预 挤 弧 次 | 图钉落下 outCubic ≤6 f,落地压扁 ≤8%、弹起 1 次、≤8 f 回稳(现 1 次 8 px,合规);落点可走弧线;引线/标签滞后图钉 3-6 f;地图底图不缩放不弹跳 |
| location_map | `map-reticle` | 缓 次 时 | 括号收拢 outCubic 12-18 f;锁定后中心点脉冲 ≤1.12 且一次(现 1.12,合规);锁定后缓推 ≤3%;过冲 0% |
| list_checklist | `list-reveal` | 缓 跟 时 | 行 stagger 2-4 f(现 5 f);行入场 12-18 f;`outBack` s ≤1.0(现 1.2);行起始缩放 ≥0.88(现 0.8);行内文字不单独缩放 |
| list_checklist | `checklist-stack` | 缓 跟 次 时 | 行 stagger 2-4 f(现 9 f,行间无重叠);落入 outCubic 12-18 f;按压缩放 ≤3%(现 3%,合规);计数角标滞后落入 3-6 f、幅度 ≤30% |
| cta_ending | `cta-lockup` | 缓 跟 次 时 | 环缩成点 `outBack` s ≤1.0(现 1.2);逐字 stagger 2-4 f(现 3 f,合规);CTA 滞后字 ≥3 f;CTA 落定后保持 ≥18 f;合规文字(机构名)不弹跳 |
| cta_ending | `wordmark-settle` | 缓 次 时 | outCubic 18-24 f;blur 18→0 与字距同曲线;下划线滞后 3-6 f;过冲 0%;保持 ≥30 f(taste §7.2 品牌停留) |

## 2A. 移动标注与连线

地图、室内跟踪、3D 卡片使用共享高分辨率固定图像标签；浮点变换定位，禁止依赖上一渲染帧的平滑。跟踪轨迹采用有限误差修正与连续速度插值，切镜分段。真实房源不得自动写样板间等示例标签。指引线绕开头像、照片、文字、人物窗口及字幕，并绘制在前景下方；绕行方位稳定，不能逐帧翻转。连续帧和编码后视频均需验收，不能仅用附着误差或成功导出替代。具体步骤见 docs/maphub-execution.md 的标注规范。

## 3. 审片清单(pass / fail)

对每条渲染结果逐条检查,全部通过才算过;任何一条失败写明文件:行号或帧号。

- [ ] 入场(位移/缩放)无 `ease.linear` / `E.linear`;`prog()`、`seg()` 省略缓动参数即为 linear,等于失败。
- [ ] 过冲 ≤4%(按 §0 量法);`outBack` s ≤1.0;弹簧阻尼比 ≥0.72。
- [ ] 回稳 ≤8 f;弹跳/震荡 ≤2 个来回。
- [ ] 房源照片、视频、合规文字:0 缩放弹跳、0 过冲、0 挤压。
- [ ] 挤压拉伸只在贴纸/图钉/价签,且 ≤8%。
- [ ] 弧线只在指针/箭头/图钉。
- [ ] 峰值缩放 ≤1.12(夸张点),数据数字脉冲 ≤1.04;元素缩放不低于 0.88(摄像机推拉不计)。
- [ ] 逐字/逐行 stagger 落在 2-4 f;同帧移动单位 ≤3。
- [ ] 价格/数字卡主动作前有 3-5 f 预备。
- [ ] 次动作滞后 3-6 f、幅度 ≤ 主动作 30%。
- [ ] 时长归档:微 5-8 f、标准 12-18 f、强调 18-24 f(8-12 f 之间的取整)。
- [ ] 关键数字落定后静止保持 ≥18 f(0.6 s);`duration_frames` ≥ §2 的时长下限。
- [ ] 每条片子夸张点 ≤1,关键词弹出 ≤3(taste §7.5)。

## 4. 已知偏差(2026-09-30 对代码的只读扫描,尚未修改,行号以扫描时的工作区为准)

**入场 linear(位移/缩放)**
- `remotion/src/shots/util.ts:19` `pop()` 用 `E.linear` 做进度;`DataNumber.tsx:10,19`(`seg` 默认 linear,缩放 0.92→1);`Overlays.tsx:40,43`(OutroCTA 线性缩放 0.9→1)。
- 默认参数陷阱:`shared/motion.ts:20` `seg()`、`effects/kit.ts:18` `prog()` 默认 linear。仅淡入的 `compare.tsx:23`、`titles.tsx:153`、`spatial.tsx:67` 属许可例外。
- 许可的持续漂移/扫描 linear(不算违规):`lists.tsx:39,71,125,151`、`numbers.tsx:77`、`compare.tsx:67`、`spatial.tsx:54,141`、`transitions.tsx:19`。
- `shared/Captions.tsx:10` 字幕用 6 f 线性淡入(`interpolate` 默认 linear),taste §7.5 要求字幕硬切。

**过冲 >4%**
- `outBack(t,1.2)` = 5.3%:`lists.tsx:46`、`lists.tsx:117`、`spatial.tsx:30`、`spatial.tsx:65`、`titles.tsx:150`(注释写"≈10%",与实际 5.3% 不符)。
- `shared/motion.ts:31` `popIn` 用 `outBack` 默认 s=1.70158 = 10%(`shared/InfoCard.tsx:111` 在用)。
- `shots/util.ts:20` `outBack(k,2.2)` = 15.4%(`RoomCard.tsx:32,46`、`LocationLabel.tsx:28,78`);`LocationLabel.tsx:47` 合成后峰值缩放 1.095。
- `numbers.tsx:24-25` 里程表锁定先冲过目标 0.5 行再回落,过冲 = 0.5 / 行程(行程 6-16 行)= 约 3%-8%,短行程时超 4%。
- `numbers.tsx:118` CountUp 落定脉冲 1.06(数据数字上限 1.04)。
- `shots/StylePresenter.tsx:19` 弹簧 damping 14 / stiffness 170 / mass 0.7,阻尼比 0.64,过冲 7.2%,且作用于讲解人视频窗口(仅 `st.motion==="spring"` 时)。

**缩放 >1.12(作用于字/卡/框的入场起始值)**
- `numbers.tsx:155` 3.2×、`numbers.tsx:157` 环 2.8×;`titles.tsx:65` 1.8×(×1.06 蠕动 = 1.91);`spatial.tsx:66` 1.75×;`lists.tsx:117` 环半径 300→40。
- 摄像机类推拉不计:`shots/MapReveal.tsx:14` 1→1.28、`shots/Media.tsx:10` pushScale 1.09。

**震荡 >2 个来回**:未发现(`spatial.tsx:98` 单次起落 8 px;`LocationLabel.tsx:47` 单峰)。

**stagger 不在 2-4 f**:`lists.tsx:46` 5 f、`lists.tsx:66` `step=9`、`compare.tsx:71` 5 f。

**保持 <18 f 风险**:`numbers.tsx` 里 CountUp 在 f40 才到目标,catalog 下限 36;`price-pop` 下限 30;odometer 类 4 位数以上在下限 60 时保持 <18 f(见 §2 时长下限)。
