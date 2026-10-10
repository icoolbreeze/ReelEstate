<!-- Paste this section into ReelEstate/AGENTS.md (or link to it) once series/map-hub/ is in the repo. -->
## Series preset: map-hub 口播 (`series/map-hub/`)

Map-driven talking-head episode for @贝壳-TV: opener (multiplane → scan → dolly zoom) lands on an illustrated Amap base map; a named cursor clicks map marks (样板间 photo cards / 小区环境 pin / 配套 POIs) to open each segment; B-roll inside segments carries scanline-annotate-focus tracking marks. Read `series/map-hub/rules/RULES.md` before changing anything visual, and `rules/mediastorm_koubo.md` for the 口播 numbers.

**Make a new episode**
1. Copy `episodes/ep07-xihu/` to `episodes/<id>/`; edit `episode.json` (listing lnglat in GCJ-02, `plane.center`, `poiQueries` with exact Amap names to `pick`). Listing facts stay marked 示例数据 until the real archive is connected.
2. `python pipeline/amap_fetch.py episodes/<id>/episode.json` — real POIs + route distances. Never invent distances or walking times.
3. Write `script.json` (lines: `layout` OPENER|A|PIP|B, `clip`, `cam`, `enter` = mark clicked before the line, `poi`, `cap` chunks, `tts`) and `shots.json` (Muse shots + annotate targets).
4. `python pipeline/build_vo.py episodes/<id>` → timeline + mix; `python pipeline/make_muse_batches.py episodes/<id> --out muse` → paste `muse/batchN.txt` into Muse; save downloads as `footage/<ID>.mp4`.
5. Per B-roll clip: `track_annotations.py grid` → write `annotations/seeds/<ID>.json` from the grid image → `track_annotations.py track --preview` → check the preview.
6. `python pipeline/sync_assets.py episodes/<id>` then `cd proj && npx remotion render src/index.ts MapHubKoubo ../out/<id>.mp4 --gl=angle`.

**Rules for agents**
- Keys: map-tools reads `~/.config/map-tools/keys.json`; never print, copy or commit keys.
- Compliance: distances only from Amap routes; no walking-time claims on screen, no 最/第一, no 学区 promises; AI footage labelled; 示例数据 tag always on.
- flova (gpt-image-2.5) runs only on the user's PC through its local MCP server (`pipeline/flova/flova_edit.js`, `$FLOVA_MCP_SERVER`, profile `$FLOVA_PROFILE`); one call per edit, `original:true`; no video generation unless the user asks; never touch invite/credit-farming scripts.
- Map edits by GPT must be re-aligned to Amap geometry (`pipeline/flova/align.py`) before use; the route must stay on roads.
- Muse presenter clips are not lip-synced: keep them muted, voice = TTS.
- Brand strip (链家 / 德佑 / 富房 / CENTURY 21) stays for the whole film; no other 贝壳 logo or "房源信息来源" line.

## Rules learned (footage pass)
- Label only visible objects, generic names, no brands/sizes unless in listing data. 2–4 per clip.
- All Muse footage tagged AI示意; generic POI footage gets clipTags 示意 · 非实拍. Presenter audio never used; presenters PiP/short, no long full-screen.
- Distances are route distances (步行/驾车 X 米), never walking times; no 最/第一/学区.
- Low-texture targets (lawn, water path, dark TV): hand-key `kf` or drop.

## Rules (v2 feedback)
- Marks first, routes on demand: never draw routes when the hub first appears; draw a route only when narration reaches its POI.
- Plain pointer only; no name tags; one cursor unless a second is truly needed.
- Click switch must be readable: glide 24 f → pause 8–10 f → press (pointer scale-down + mark depress + ripple) → 15–20 f open from the mark; return 18 f. Budget the script gaps for it, keep total ≤ ~95 s.

## Rules (v3 feedback)
- Every mark explained later must already be on the opener's final map (staggered, title readable, no routes); the hub continues with the same marks, no re-pop. Off-frame marks sit at the frame edge.
- Before each click push the camera toward the target; cursor ~1.7× default; press + ripple play ~10–12 f before the clip opens.

## Rules (v4 feedback)
- Opener end marks must read at 1440 and at a 50% thumbnail: pins ≥ 64 px, labels ≥ 24 px, cards ≥ 200 px wide; no overlaps (collision avoidance + leaders); title block always clear; camera settled ≥ 0.5 s before the end.
- Ripple: thick accent ring + white/dark outline, ~80–120 px radius, drawn above the opening clip; clip opens only after the ripple is ~70% expanded. Push-in ~1.6× before the press. Verify every click (all enters + inserts), not one sample.

## Rules (HeyGen avatar)
- Avatar on camera only on A/PIP lines + hook; HeyGen render <= 55 s (free plan 60 s): one 16:9 render lip-synced to OUR audio, split by heygen_plan.py.
- Label "AI数字人 · AI合成声音" whenever the avatar is on screen, and once on the end card. Never use HeyGen/Muse audio in the mix.
- Hook 3-5 s, listing highlights only, 示例数据 tag on screen, hard cut into the opener; opener timing/text unchanged.

## Rules (v3)
- Hook shows listing highlights as cards beside the avatar; don't repeat the hook in the opener/first line.
- Ending = summary panel (account, every highlight, franchise brands 链家/德佑/富房/CENTURY 21/中环) with the avatar in small PiP + the AI数字人/AI合成声音/示例数据 line.
- Brand logos: official source recorded in brands.md, extracted uncropped; a typeset placeholder must be flagged `placeholder: true` and replaced before publishing.

## Rules (v4)
- Brand-strip-only episodes: set onScreenNotes=false; keep required disclosures in the voice-over (示例房源, AI示意 where generic footage is used).
- Hook list sits behind the matted avatar; never place cards over the person.
- Anything runnable on the user's PC (CosyVoice clone, rembg matting) goes through grok CLI there; bring results back with CopyToBox.
