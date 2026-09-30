# rules/taste.md: video-taste（审美规则：taste-skill 的视频量化版）

> **本文件对所有 Agent（Codex / Claude Code / OpenCode / ZCode）强制生效。** 写 `shots.json` / 改 Remotion 镜头组件 / 渲染之前必须先读完；渲染后必须按 §8 做静帧 harmony 检查并人工看图。`[HARD]` 项违反即阻断交付。
>
> **上游 / Upstream:** 本文改编自 [taste-skill](https://github.com/Leonxlnx/taste-skill)（Leonxlnx，MIT © 2026），固定在 commit `ce26fc2`（`skills/taste-skill`、`skills/redesign-skill`、`skills/soft-skill`）。许可证全文见同目录 [`LICENSE-taste-skill.txt`](LICENSE-taste-skill.txt)。简报推断、三个 dial、反 AI 默认禁令、redesign 审计协议、Editorial Luxury 原型来自上游；"VIDEO ADDS" 部分为本仓库新增，与上游作者无关。
>
> taste-skill 面向网页。视频帧没有 hover / scroll / 响应式断点，但有固定画布、平台 UI 遮挡、时间与镜头。本文保留上游的判断力，把网页机制换成**脚本或静帧能验证的数字**。
>
> **仓库落地（本仓库的绑定方式）**
> - 检查脚本：`pipeline/check/harmony_check.py`（numpy + Pillow；Windows 下自动 UTF-8 输出）。
> - 触发：`npm run still -- projects/<cat>/<id> --frame N`（≥4 个不同镜头）→ `npm run check -- projects/<cat>/<id>`（自动扫描 `output/` 下的静帧并跑 harmony）；交付前用 `npm run check -- projects/<cat>/<id> --require-taste`（无静帧即失败）。只跑审美检查：`npm run check:taste -- projects/<cat>/<id>`。
> - 硬失败（FAIL）阻断交付；软警告（WARN）要在交付说明里写明处理或理由。

Every rule is contextual (upstream principle): read the brief first, then pull only the rules that fit. Hard rules marked **[HARD]** block delivery.

---

## 0. Brief inference and Design Read (upstream §0, adapted)

Before touching a composition, read: **video kind** (location/配套 map, 户型 tour, parameter card, talking head + b-roll, brand opener), **platform** (Douyin / 视频号 / Bilibili / YouTube), **audience**, **vibe words and references** (named creators, pasted frames), **existing brand assets** (accent, fonts, logo), and **quiet constraints** (legal labels such as 示意图, data attribution, 审图号 rules for maps, no invented numbers).

Output one line before building:
**"Reading this as: \<video kind> for \<audience> on \<platform>, with a \<vibe> language, leaning toward \<preset from §1.B>."**

Example: *"Reading this as: real-estate location explainer for Douyin home buyers, with a MediaStorm product-intro language, leaning toward the mediastorm-explainer preset."*

If the read genuinely forks, ask **one** question. Otherwise declare it and proceed.

### 0.1 Anti-default discipline (upstream §0.D, 4.2, 9, video extensions) [HARD]
Do not ship these defaults unless the brief explicitly asks for them:
- AI purple/blue gradients and glows (the "Lila rule"); neon outer glow on text.
- Inter + slate-900 as the whole type system; centered hero over dark mesh as the default opener.
- Three equal feature cards in a row (video form: three identical info cards entering in lockstep).
- Glassmorphism on everything. Allowed on at most one layer family (e.g. the attribution chip) and only with a solid-fill fallback that still passes contrast.
- Infinite loop micro-animations on everything (pulsing every dot, floating every card).
- Pure `#000` / pure `#fff` surfaces: use off-black (`#141214`) and off-white (`#FBFBF8`).
- Decorative status dots before labels, em-dash (`—`) or en-dash separators in on-screen text, more than one middle dot (`·`) per line.
- Hand-rolled icon paths. Use one library family (Tabler / Phosphor / Radix; Lucide only on request), one stroke width.
- Premium-consumer beige+brass+espresso palette as the reflex for "luxury real estate" (upstream 4.2 ban list applies verbatim).
- Model-drawn text inside generated images. All readable text is overlaid in code.
- Fake-precise numbers. Every distance, time, price or percentage traces to real data (API, brief, document) or is visibly labeled 示例/mock.

---

## 1. The three dials (upstream §1), with video meaning

| Dial | 1 | 10 | What it controls in video |
|---|---|---|---|
| `DESIGN_VARIANCE` | symmetric, centered, static grid | asymmetric, broken grid, bold crops | layout asymmetry, camera angle freedom, crop aggressiveness |
| `MOTION_INTENSITY` | near-static holds | cinematic physics | camera travel, entry energy, overshoot, beat impacts (§7 caps) |
| `VISUAL_DENSITY` | one message per frame | cockpit | simultaneous labels, info cards on screen, words per card |

### 1.A Video dial bands (numeric)
| Band | VARIANCE | MOTION (per 10 s) | DENSITY (on screen at once) |
|---|---|---|---|
| 1-3 | centered, symmetric, 0-5° tilt | ≤4 entry events, camera push ≤0.6%/s, no overshoot | ≤2 text blocks, ≤12 CJK chars per block |
| 4-7 | offset thirds, 15-35° plane tilt | 5-10 entry events, springs damping ≥14, ≤1 beat impact | 3-5 text blocks, ≤20 CJK chars per block |
| 8-10 | asymmetric crops, bleed, 35-50° tilt | 10-14 entry events, overshoot allowed ≤12%, ≤2 impacts | 6-8 text blocks (data scenes only) |

### 1.B Presets (upstream §1.B, mapped to our styles)
| Preset | VARIANCE | MOTION | DENSITY | Signature |
|---|---|---|---|---|
| `mediastorm-explainer` (影视飓风 product-intro / location label) | 6 | 6 | 4 | one lemon accent `#D6EB00`; `{ 花括号 }` location title; card enters 4-12 f; hard cut exits; −16 LUFS |
| `mediastorm-space-tour` (空间参观 room cards) | 5 | 5 | 3 | italic heavy CJK room title 150-180 px; floor-plan locator lower-left 450×170 @4:3 |
| `qiuzhi-explainer` (秋芝2046 knowledge style) | 5 | 5 | 5 | light canvas, one warm accent, schematic line art, number cards; friendlier radii |
| `editorial-luxury-card` (soft-skill archetype) | 4 | 3 | 2 | see §9; for premium listing info cards only |
| `redesign-preserve` | match | match+1 | match | audit first (§2) |
| `redesign-overhaul` | +2 | +2 | match | keep content/data, replace visual language |

**Motion claimed = motion shown** (upstream §5): a MOTION ≥4 preset with a ≥1.0 s fully static window fails (§7.4). **Motion must be motivated**: each animation answers hierarchy, storytelling, or state change in one sentence, or it is removed.

---

## 2. Redesign protocol: audit before touching (upstream §11 + redesign-skill)

1. **Detect mode**: greenfield / preserve / overhaul.
2. **Scan**: read the composition code, list layers (back to front), assets, fonts, tokens, timings.
3. **Diagnose** with this video audit, writing one line per finding:
   - Brand tokens: accent(s), inks, radii, fonts. More than one accent? Mixed warm/cool greys? Pure black/white?
   - Layer stack: any two equally detailed layers of the same kind (§5.1)? Pasted edges? Mismatched scale/perspective?
   - Labels: more than one label family (dark chips next to light cards)? Decorative dots? Separator overload?
   - Contrast: every readable string measured (§3.3).
   - Safe areas and collision zones (§4).
   - Motion: easing, simultaneous animators, static windows, loops without purpose.
   - Data honesty: every number traced to a source.
   - **Dial reading** of the existing piece. That is the starting point, not the baseline.
   - Run `pipeline/check/harmony_check.py` on the *current* stills to get the baseline score.
4. **Fix in upstream lever order**, stopping when the brief is met: (1) type, (2) spacing/safe areas, (3) color recalibration, (4) motion layer, (5) recomposition of the key shot, (6) asset replacement. Regenerating a model image is lever 6: only when code cannot fix it.
5. **Never change silently**: data values, legal labels (示意图, attribution, 审图号 lines), brand wordmark, the user's chosen accent.

---

## 3. Palette and contrast (upstream §4.2 made numeric, VIDEO ADDS)

### 3.1 Role ratios (60-30-10, measured on the frame)
| Role | Area share | Use |
|---|---|---|
| Primary (canvas / ground) | 50-70 % | background, ground plane |
| Secondary (structure) | 20-35 % | roads, buildings, cards |
| Accent (single signal) | 3-12 % | route, key label, pin |
**[HARD]** accent >18 % of frame, or a second non-semantic signal hue >4 %.

### 3.2 Hue and value bands (HSV 0-1)
- Chromatic signal hues (S ≥0.25): ≤4 per frame, ≤3 per piece (1 accent + semantic pos/neg). **[HARD]** ≥6 in any frame.
- Accent S may exceed upstream's "<80 %" when it is the brand's own color (e.g. `#D6EB00`, S≈1.0). Then everything else stays S ≤0.45 so the accent owns saturation.
- Light canvas V 0.85-0.98, S ≤0.12. Dark canvas V 0.05-0.18.
- **Derived tones, not new hues**: when the accent is too light to read on the canvas, derive a same-hue deep tone (e.g. `#8FA300`, `#46500A`) for strokes and casings instead of reaching for black.
- Shadows tinted to the scene (e.g. `rgba(38,48,58,.16)`), never `rgba(0,0,0,.3)`.
- **[HARD] forbidden combos**: black strokes >1.5 px across a pale canvas (V>0.85); dark chips (V<0.25) on a pale map for scale/ring labels; accent text on accent fill; red+green as a non-semantic pair.

### 3.3 Contrast (WCAG 2.1 AA, measured on rendered pixels)
| Text | Min |
|---|---|
| ≤32 px effective (captions, attribution, micro) | 4.5:1 |
| ≥36 px or ≥24 px bold | 3.0:1 |
| Icons, route vs ground (focal third) | 3.0:1 |
Never stack opacity on an already-muted ink. Pale scene: off-white card ≥0.92 alpha + ink `#141214`/`#3A3D42`. Dark scrim + white text only when background V under the text ≤0.45.

---

## 4. Canvas, safe areas and collision zones (1440×1080, 4:3) (VIDEO ADDS)

1920-wide references transfer 1:1 vertically and ×0.75 horizontally.

| Zone | Rule |
|---|---|
| Action-safe | all readable UI ≥48 px from every edge (prefer 60) |
| Title-safe | hero/display text ≥72 px from top, ≥96 px from sides |
| Platform bottom UI (Douyin / 视频号 landscape) | no permanent chrome in bottom 150 px |
| Platform right UI | no permanent chrome in right 96 px |
| Caption band | y 780-1000, centered, max width 1150 px; nothing else readable inside while a caption or location title is on screen |
| PiP / host window | lower-left preferred, ≤360×480, ≥48 px margins; never overlaps the focal subject or caption band; face box keeps ≥40 px clearance from any text |
| Legal / attribution | top-left inside action-safe, max width 780 px, micro ≥13 px |
**[HARD]** any readable element outside action-safe, or two readable elements overlapping. Projected labels (3D billboards) are clamped to `[SAFE, W−SAFE]` in code. When a caption or title lands, colliding labels yield (fade ≤10 f) rather than overlap.

---

## 5. Layering, depth and composition (VIDEO ADDS)

### 5.1 Single-world rule [HARD]
**Never stack two equally detailed layers of the same kind** (map on map, photo on photo, UI screenshot on UI screenshot). Allowed:
- **One continuous world**: a single detailed layer that extends into distance by atmospheric perspective (blur ↑, saturation ↓, haze toward a tint color). No second sharp copy at another scale.
- **Subject over atmosphere**: sharp subject; background is gradient, mesh, or the same source defocused (blur ≥12 px).
- **Evidence card on bed**: framed screenshot/photo with one tinted shadow; bed dimmed/desaturated.

### 5.2 Depth channels (use ≥2)
| Channel | Near (focal) | Far |
|---|---|---|
| Blur @1080 | 0 px | ≥6 px (atmosphere 12-30) |
| Saturation | 100 % of palette | ≤70 % of near |
| Value | full local contrast | compressed to within ±0.08 of haze tint |
| Edge density (Sobel) | highest | ≤60 % of near |
Atmosphere is directional: the side toward the camera keeps contrast; the horizon side takes the haze. Sky color = haze color, so no horizon line is drawn.

### 5.3 Composition
- One focal subject per beat (12-35 % of frame in mid beats). Two equal-weight subjects fail.
- One horizon per shot; the plane tilt stays in one range for the take (e.g. 22-48°).
- No pasted edges: any inset plane feathers over ≥8 % of its size or dissolves into the world.
- **One label family**: all info labels share one card material, radius and shadow. The only exception is the single accent slab for the hero label.
- **Shape lock** (upstream 4.4): one documented radius rule, e.g. cards 14 / chips 10 / accent slab 0 (skewed).

---

## 6. Type scale, Chinese + Latin (1440×1080) (VIDEO ADDS)

Effective pixel height = fontSize × ancestor scales × perspective (measure on the frame, not in code).

| Token | px | Weight | Line-height | Tracking |
|---|---|---|---|---|
| hero | 110-180 | 800-900 | 1.05-1.12 | CJK 0; Latin −0.02 em |
| display | 72-110 | 700-800 | 1.10-1.18 | CJK 0; Latin −0.01 em |
| headline | 48-64 | 700 | 1.15-1.25 | 0 |
| tagline (POI name) | 25-40 | 700-800 | 1.15-1.30 | 0 |
| body (POI detail) | 18-28 | 500 | 1.25-1.50 | 0 |
| caption | 15-21 | 600-700 | 1.2-1.4 | 0 |
| micro (legal) | 13-15 | 500 | 1.3-1.4 | 0 |
Rules: ≤3 hierarchy levels on screen; hero:body ≥2:1; one hero per frame; CJK never gets negative tracking; italic Latin with descenders needs line-height ≥1.1 (upstream 4.1); emphasis by weight/italic of the same family, no random serif word (upstream serif discipline); readable narrative text ≥5 % of H (≥54 px), helper ≥3 % (≥32 px) at phone size (check by viewing the frame at 390 px wide). Numbers use `tabular-nums`.

---

## 7. Motion (Remotion) (VIDEO ADDS)

### 7.1 Curves
| Use | Curve |
|---|---|
| Entry | `Easing.bezier(0.16,1,0.3,1)` or `spring({damping:14-20, stiffness:100-200, mass:1})` |
| Camera / continuous | `Easing.bezier(0.65,0,0.35,1)` or in-out sine; never ends at zero velocity on the last frame |
| Pop / punch | overshoot ≤12 %, settle ≤9 f |
| Banned | linear on UI entries; random jitter; line boil; `Math.random()` (non-deterministic renders) |

### 7.2 Durations @30 fps
Card/chip entry 5-12 f · title brace open 8-14 f · route draw 30-60 f · camera move = shot length · key-info hold ≥15-30 f · brand hold ≥30 f · exit ≤ entry (hard cut preferred).

### 7.3 Density caps
- ≤5 elements animating at the same frame (camera counts as 1).
- Entry events per 10 s: by MOTION band (§1.A).
- Full-frame impacts (flash, slam, whip): ≤3 per piece.
- Perpetual loops: ≤1 family on screen (e.g. the pin ripple) and only when it carries state.

### 7.4 Anti-slideshow
Every shot has a camera or subject motion channel. **[HARD]** no fully static window ≥0.8 s (ffmpeg `freezedetect=n=0.003:d=0.8`), except declared holds covered by a slow camera.

### 7.5 Effect rotation (shotcraft / talkcraft constraints)
- One animation technique is the star at most **once** per piece; a card family reuses one skin.
- Keyword pop on subtitles ≤3 per piece; subtitles themselves hard-cut, no animation, no punctuation.
- Never mix bounce emphasis and editorial type-contrast emphasis in the same sentence.
- Highlights/sweeps ≤1 per shot, clipped to the element's radius.
- The same transition style does not run on two consecutive cuts.

### 7.6 Motion feel (Disney principles)
See [`rules/motion.md`](motion.md): numeric motion-feel rules (easing, anticipation, overshoot ≤4%, settle ≤8 f, stagger 2-4 f, key-number hold ≥18 f), a per-effect table for all 19 catalog effects, and a review checklist. Where it is stricter than §7.1 / §1.A (overshoot, settle), motion.md wins.

---

## 8. Post-render harmony check [HARD]

1. Extract **≥4** stills (prefer 5-8) at meaningful beats, one per distinct shot (not only hero frames): `npm run still -- projects/<cat>/<id> --frame N` (writes `output/<id>_<ratio>_fN.png`), or `ffmpeg -ss`. Delete stale stills after every re-render.
2. Run (either is fine; the first is what agents normally use):
   ```powershell
   npm run check -- projects/<cat>/<id> --require-taste
   npm run check:taste -- projects/<cat>/<id>
   python pipeline/check/harmony_check.py output/*.png --accent '#D6EB00'
   python pipeline/check/harmony_check.py --dir projects/<cat>/<id>/output --glob '*_f*.png'
   ```
   Needs Python 3 with `numpy` and `Pillow` (opencv is not required by the script).
3. The script reports per image: k-means palette (5 clusters, hex + area), chromatic hue count, accent area, top/mid/bottom mean S and V, peripheral/center edge density, double-detail detection, far-band detail ratio, far/near saturation ratio, dark-chip blocks on a bright canvas, and a text-like contrast estimate (median and p15).
4. Checklist:

| ID | Metric | Pass | Severity |
|---|---|---|---|
| P1 | accent area | ≤18 % (ideal 3-12) | hard |
| P2 | chromatic hues | ≤5 | hard |
| P3 | largest cluster | ≥50 % | soft |
| C1 | text-like contrast median | ≥3.0 | hard |
| C1b | contrast p15 / median | ≥4.5 | soft |
| D1 | periphery / center edge | ≤0.85 | soft |
| D1h | periphery / center edge | <1.05 | hard |
| D2 | double-detail (≥3 high-edge quadrants, balanced top/bottom) | none | hard |
| D3 | far-band (y 11-28 %) / center edge density | ≤0.30 | hard (single-world check) |
| A1 | far / near saturation | ≤0.95 | soft |
| L1 | dark-chip blocks on bright canvas | ≤1.5 % | hard |
| T1 | mean V in light (0.70-0.98) or dark (0.05-0.25) band | yes | soft |

5. **PASS = zero hard fails across all stills.** Then *look at the stills yourself*: the script catches regressions, not taste. A pass with a visible pasted edge, watermark, collision, or second map is still a FAIL.
6. Fail → fix (prefer code) → re-render stills → re-run → look again.

---

## 9. Editorial Luxury info card (soft-skill archetype, one option)

For premium listing cards (price / area / layout), not for map POI chips:
- Large display number in a neutral sans (serif only with a stated brand reason; never Fraunces / Instrument Serif), CJK label beneath at body size.
- Double-bezel (soft-skill 4.A): outer shell 1 px tinted hairline + 6-8 px padding, inner core radius = outer − padding.
- Grain overlay ≤3 % opacity on a static layer only.
- Palette rotation: avoid the cream+brass+espresso reflex; pick Cold Luxury, Forest, Olive+Brick+Paper, or monochrome + the brand accent.
- Motion: one heavy fade-up (translateY 16-24 px, 18-24 f, `bezier(0.32,0.72,0,1)`); no stagger of more than 4 lines.

---

## 10. Pre-flight (upstream §14, video version)

- [ ] Design Read line written; dials set and justified; preset named.
- [ ] Redesign mode detected; audit written; baseline harmony score recorded.
- [ ] One accent, derived tones only; no pure black/white; shadows tinted.
- [ ] Zero em-dash / en-dash separators; ≤1 `·` per line; no decorative dots.
- [ ] One label family, one radius rule, one icon library.
- [ ] Single-world layering; no pasted edges; one horizon.
- [ ] All readable text in code (none model-drawn); contrast measured.
- [ ] Safe areas and caption/PiP collision zones respected.
- [ ] Motion caps, easing, no static window ≥0.8 s, effect rotation respected.
- [ ] Every number traced to data; legal labels and attribution present and unchanged.
- [ ] `harmony_check.py` PASS (via `npm run check`) **and** a visual pass on every still.

---

## Credits and license
- Upstream: <https://github.com/Leonxlnx/taste-skill>, commit `ce26fc2`, MIT. License text: [`rules/LICENSE-taste-skill.txt`](LICENSE-taste-skill.txt) (keep it alongside this file).
- taste-skill © 2026 Leonxlnx, MIT: brief inference, dials, anti-default bans, redesign protocol, pre-flight structure, Editorial Luxury and double-bezel from soft-skill.
- Video rules draw on public practice: WCAG 2.1 AA contrast, Material 3 contrast levels, 60-30-10 color balance, Gestalt figure-ground, and film atmospheric perspective.
