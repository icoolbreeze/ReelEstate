# RUNBOOK — map-hub 口播 series (end to end, for the local grok agent)

> **现行生产入口**：先读 [PRODUCTION.md](PRODUCTION.md)，运行 `npm run doctor`。xihu 测试工程已删除；新建使用 `templates/listing/episode.json`，旧 project.json 生产入口已移除。房源正式输出使用独立 `compliance.json`，缺少真实发布资料仍会阻断。

> **2026-10-24 架构入口更新**：先读 [architecture.md](architecture.md)。房源期改用 `projects/listing`，`projects/map-hub` 联接已于 2026-10-30 移除；正式期号由两类内容共用，`purpose: test` 不占号。Python 公共能力位于 `pipeline/common`，字体、标签防抖、跟踪、指引线、品牌和媒体组件位于 `templates/shared/remotion/src`。依赖只在 `tools/remotion` 管理，使用根目录 `npm run setup/typecheck/check/render/still`；旧命令继续兼容。原始素材不参与清理，渲染输出和 public 更新必须原子替换。其他制作与发布规则保持有效。

Series: @贝壳-TV map-hub 口播. 1440×1080, 30 fps, −16 LUFS. A satellite-style map is the hub: listing pin, real-listing room cards,
小区环境, POI pins; a cursor clicks a mark → the clip opens out of it → back to the map. HeyGen avatar ("Cool Breeze") on camera
(hook full screen, then PiP), cloned voice for everything.

Code: `templates/map-hub/remotion` (Remotion) + `pipeline/maphub/*.py`. Rules: `rules/map-hub/`. Example: `projects/listing/ep02-zidong`.
All commands run from the repo root `C:\Users\shipi\vswp\ReelEstate` in PowerShell. `<EP>` = `projects\listing\epNN-<slug>`.

One series, many episodes. Each episode has its own folder. Voice-clone references, the Cool Breeze profile, fonts, and brand logos stay shared and are not copied in.

| | Path |
|---|---|
| This episode's footage, voice wavs, HeyGen export, matte, map, script, output | `projects/listing/<ep>/` |
| Folder name | `ep08-xihu`, `ep12-xihu`, `ep10-yuedu`. Category and layout stay in `episode.yaml` |
| CRM listing id | `<ep>/episode.yaml` `listing.ref` and `<ep>/data/listing_ref.json` only |
| Chinese community name | `episode.yaml` `listing.community` |
| Voice reference | `assets/presenter/cool-breeze/voice/ref_phone_v1.wav` + `ref_phone_v1.txt` (default, also the IndexTTS emotion ref). Fallback: `voices/clone/reference.wav` + `reference.txt` (old HeyGen, read-only) |
| Presenter | `assets/presenter/cool-breeze/presenter.yaml` |
| Fonts and brands | `templates/map-hub/shared/public/{fonts,brands}` |

Categories: `rental` 租赁, `resale` 二手房, `new-home` 新房, `knowledge` 房源知识与市场分析. The user does not create folders. They give a listing id, or a new-home 楼盘 name, and the agent runs section 0. Rental and resale store that id. New-home has no listing id. Knowledge uses a topic. `ep07-xihu` keeps its original folder name. The cloud listing API currently answers rental only.

> **Read [`CONVENTIONS-shared.md`](CONVENTIONS-shared.md) first** (先读共用规范): output folders/naming, voice, HeyGen, captions/badge, visuals, asset generation, Kaggle, QA, covers, compliance. This runbook keeps only listing-specific steps and commands. Covers: CONVENTIONS section 9 (default = reuse Cover.tsx + existing presenter backgrounds, change text only; new flova background only on request).

## 本类型独有（房源类 / listing）
- Frame **4:3 1440x1080**; HeyGen export goes through **7b `heygen_43.py`** (de-watermark + outpaint to 4:3), not the knowledge 16:9 path.
- The **map is the hub** (Amap `map.py` POIs/routes, flova restyled base, click-to-open clips, routes drawn only when narrated); listing data from CRM (`docs/crm.md`); footage naming `docs/FOOTAGE-SPEC.md`; scanline annotations.
- Presenter **full screen only in the hook** (matted, text behind the person), then **PiP**; END = small PiP + summary panel + brand row.
- Voice fallback: flova -> IndexTTS-2.5 on Kaggle -> local F5.
- Sign-off "我是贝壳TV，我们下期见"; say 示例房源 once; generic B-roll -> "画面仅作示意"; AI images never used for floor plans / real rooms / landscape / surroundings (exceptions: step 5a, Muse enhancement of this listing's own original footage, nothing added or removed; step 5b, flova cleanup of this listing's own CRM floor plan, same walls/rooms/areas).
- Palette and brand follow CONVENTIONS-shared.md (warm light, no cyan/blue; bottom brand strip kept). The old fluorescent-green / hard-cut mediastorm look in `one-sentence-workflow.md` is superseded.
- 实拍素材图片优化交给 **Muse**（不用 flova），由 bot 在 box 浏览器完成：原始素材 + 一条完整提示词，原生 2096x1184，不增删物品，见 **5a**（2026-10-19）。

## Execution update (2026-10-12)
See `docs/maphub-execution.md`: per-episode `work/remotion`, configurable executor, IndexTTS primary / explicit F5 backup, wav-bound word timestamps, and technical preflight before render. Never switch the shared template links. Existing estimated captions are draft-only; align normalized wavs before a final rebuild.

## Hard rules (stop and ask the user if a step would break one)
- Only the user's own HeyGen avatar ("Cool Breeze") and the user's own cloned voice. Never upload, edit, move or delete the
  user's raw recordings (`voices/clone/*` reference audio, `avatar/` source clips) — read-only.
- Never touch `.mcp.json`, `.grok/`, `~/.config/map-tools/keys.json` (never print keys). No git commit/push unless asked.
- Every episode is self-contained under `<EP>/`; never reference another episode's files. Heavy media is gitignored.
- HeyGen free plan: ONE landscape 16:9 video per episode, ≤ 60 s (our budget 55 s), 720p. Spend credits only once per episode;
  if a generation fails, report instead of retrying more than once.
- Facts only from listing data + map.py results. No 步行X分钟, no 最/第一/唯一, no 学区/入学 promises, no invented brands/sizes.
  Listings are real (`sample_data: false` by default): facts only from CRM / Amap / developer docs, follow rules/compliance. 示例数据 only if the user explicitly asks for simulated data.

## Shared resources
- Presenter profile `assets/presenter/<name>/presenter.yaml` (default `cool-breeze`): HeyGen avatar/look/audio-upload rule, voice
  engine + ref wav/text + seed/speeds + Whisper threshold, Muse avatar ref, matting settings. Resolve settings as
  presenter.yaml, then episode.yaml `presenter_override`. Media in `media/` (gitignored); voice refs read-only.
- Fonts/brands: `templates/map-hub/shared/public/` (shared, linked by stage.py).

## 0. New episode (fixed workflow)
    scripts\new_episode.cmd --category rental --slug xihu --listing <id> --title 小区名 [--footage <dir>]
    scripts\new_episode.cmd --category new-home --slug xipai --title 楼盘名 [--footage <相机文件夹>]
    (knowledge: scripts\new-knowledge-episode.cmd --slug yuedu --topic 选题)
The agent picks the next episode number when `--episode` is omitted. Creates `<EP>/episode.yaml`, `episode.json` (sample numbers cleared; rental `listing.rent`, resale/new-home `listing.price`), `footage/raw/` (camera names kept) + `footage/raw_manifest.json`, `footage/assets/` per category (rental/resale `floorplan,photos,map`; new-home `brochure,renderings,sandtable,map` + `sources/docs/`) + README (docs/CONVENTIONS-shared.md §6a), `consent/`, plus `data/listing_ref.json` (rental/resale). New-home has no data file: the 楼盘 name is `listing.community`. Other folders are created on first write. Footage rules and the full layout: docs/FOOTAGE-SPEC.md.
A listing id never goes in the folder name or in `episode.json`. New-home has no listing id. Stage 1 reads `listing.ref` for rental and fills facts from BeikeMicroservice.
Then say `做视频 <id>` to grok, or `scripts\make-video.cmd <id> [stage]` (detached, resumable, logs in `<EP>/jobs/`).
Use the independent templates/listing/episode.json; do not copy another episode by hand. `python pipeline\maphub\stage.py <EP>` prepares this episode's isolated Remotion workspace.
Check: `<EP>/work/remotion/public` and `src/episode` point only into `<EP>`. Shared template links are left untouched.

## 1. Listing data (BeikeMicroservice crm_connector)
- Follow `docs/crm.md` (service on 127.0.0.1:8020; `python pipeline/common/crm_listing.py <EP>` writes `data/listing.json` + `data/listing_prospect.json`, allowlisted fields only).
- Pick one listing; fill `<EP>/episode.json` → `listing` (community, layout, area, rent, tags, address, photo kind) and
  `<EP>/data/listings.json` (`chosenId`, `mid[]`) in the ep07 shape.
Check: every number on screen traces to this JSON.

## 2. POIs and routes (map.py)
    python pipeline\maphub\amap_fetch.py <EP> --city 杭州
Uses `~/.agents/skills/map-tools/scripts/map.py` (or `$MAP_TOOLS_PY`); keys are read by map.py itself.
Writes `<EP>/pois.json`, `pois.md`: metro, schools, supermarket, mall, hospital, park with route distance (walking; hospital driving).
Map base: `<EP>/map/` + `data/mapdata.json`, `sat.json`, `hub.json` (room-card offsets, env pin, clipTags) — copy ep07's and
re-fit the plane (`episode.json mapPlane`, center lng/lat, z15) — GCJ-02 ⇄ WGS-84 via `pipeline/maphub/coords.py`.
Check: distances in pois.md are route distances (not straight-line); no POI > 2 km unless phrased "约".

## 3. Script (`<EP>/script_vN.json`)
Shape = `ep07-xihu/script_v5.json`: `hook` {id, clip, tts, cap[]} + `lines[]` {id, layout OPENER/A/PIP/MAP/B/END, onCam A/PIP/VO,
clip, enter (mark id → click), poi[], insert, gap, cam, tts, cap[]}.
- 影视飓风 tone: short clauses, commas for breaths, punchy beats; hook 3–5 s of highlights (rent, layout, 2 material points, metro distance).
- Map order: OPENER → hub intro (PIP) → 房间 rooms (click each card) → 小区环境 → 周边 (metro, schools, market, mall, hospital, park)
  → summary → END panel (PiP + list + brands) → sign-off "我是贝壳TV，我们下期见".
- On camera: hook + ~6–7 PiP lines; on-camera speech + 0.5 s gaps ≤ 55 s (measured after voice, step 4).
- Spoken compliance: say 示例房源 once; generic B-roll (park/market) → "画面仅作示意".
Check: `python pipeline\maphub\build_vo.py <EP> --script script_vN.json` (edge-tts estimate) prints total ≈ 90–130 s.

## 4. Voiceover (DEFAULT: flova MiniMax Speech 2.8 HD, voice Gentle_Youth)
Default since 2026-10-12: `C:\ProgramData\miniconda3\python.exe scripts\voice\clone_tts.py <EP>\voice\narration.json --episode <EP> --out <EP>\voice\flova_minimax`. It calls the flova MCP `generate_speech` tool with profile kid4 (about 10 credits per line) and writes -16 LUFS wavs. Default whole-passage mode: ONE call (about 10 credits) -> `passage.wav` + `passage.json`, sped up with `atempo` 1.1 (presenter `tempo`, pitch kept). Use light rhythm punctuation. The offline post-steps then run automatically: `passage_timings.py` (Whisper plus fuzzy alignment), `retime_pauses.py` (。 0.42 s / ， 0.31 s / section 0.6 s, ±15%, `pause_after` per line), then `passage_timings.py --split`, which writes `timings.json` plus per-line `<id>.wav`/`<id>.json` for `build_vo.py --alignment-dir <dir>`. Skip with `--no-retime` / `--no-timings`. Check `match_ratio` in timings.json and the Whisper text; if a sentence is wrong or missing, regenerate that section only (`--mode line` on a sub-script). Never use `——`/`--` in text (it is read aloud); use `，` or `…`. If flova fails (exit 21), use the IndexTTS-2.5 Kaggle path below. Local F5 is the last resort (`--auto-fallback`).

### 4b. Fallback: voice clone (IndexTTS-2.5 on one Kaggle T4)
Engine/seed/speeds from the presenter profile (IndexTTS-2.5, seed 22, 1.05 on-camera / 1.0 VO; CosyVoice rejected as flat). `scripts\voice\push_indextts25.py`, docs `docs/kaggle-gpu.md`. F5 (`scripts\voice\clone_tts_f5.cmd`) only when explicitly requested. edge-tts in section 3 stays the timing estimate.
- Write `<EP>/voice/narration.json` {engine:"indextts25", ref_wav:"assets/presenter/cool-breeze/voice/ref_phone_v1.wav", ref_text:"assets/presenter/cool-breeze/voice/ref_phone_v1.txt",
  lines:[{id, text, seed, speed, emo_ref:"ref_phone_v1.wav", emo_alpha:1.0}]}; one entry per hook + line (or 2-3 large sections; whole passages give the most natural prosody);
- Pauses come from punctuation and line breaks only. Never use `——` (it is read aloud); use `，` or `……`. See docs/voice-style-mediastorm.md.
  text = tts with rhythm punctuation. Flat `text` only.
- Speed 1.0–1.1 still means faster when greater than 1. The kernel converts `duration_factor = 1/speed`. No post time-stretch unless the on-camera budget forces it (then atempo ≤ 1.1).
- For HOOK and on-camera lines generate 2–3 seeds; pick by ear / Whisper score. T4 runs fp32.
      C:\ProgramData\miniconda3\python.exe scripts\voice\push_indextts25.py --episode <EP> --script <EP>\voice\narration.json
      C:\ProgramData\miniconda3\python.exe scripts\kaggle\pull_job.py --episode <EP> --job tts --run indextts25
- Wavs land in `<EP>/kaggle/tts/indextts25/output/out/<id>.wav` (22050 Hz) plus `manifest.json`.
- Post: trim silence, loudnorm −16 LUFS → `<EP>/voice/final/<id>.wav` (ffmpeg `silenceremove…,loudnorm=I=-16:TP=-1.5:LRA=7`).
- Whisper check (`pipeline/asr` or the cosyvoice venv's whisper): similarity ≥ 0.85 per line, otherwise re-roll the seed.
      python pipeline\maphub\build_vo.py <EP> --script script_vN.json --voice-dir <EP>\voice\final
      python pipeline\maphub\heygen_plan.py <EP> plan
Check: heygen_plan prints "HeyGen video ≤ 55 s"; `<EP>/heygen/heygen_audio.wav` + `heygen_segments.md` exist.

## 5a. 实拍素材图片优化 / listing still & photo enhancement (Muse, box browser) — decided 2026-10-19
Run after section 0 (footage in `footage\raw\`, shots picked) and before 5/6/9 (clips, annotations, assemble). Tool: **Muse** (muse.ai chat agent) in the **box browser** (user is logged in), done by the bot via computerUse. **Not flova.**
Folders (originals stay untouched in `footage\raw\` and `footage\raw\photos\`):

| | Path |
|---|---|
| Inputs sent to Muse (full-res stills extracted from raw clips, copies of chosen photos) | `<EP>\drafts\muse_test\src\<room>_still_t<sec>.png`, `<room>_photo_<file>.jpg` |
| Trial outputs and side-by-side comparisons | `<EP>\drafts\muse_test\<round>\`, `<EP>\drafts\muse_test\cmp\` |
| Accepted outputs (used downstream) | `<EP>\footage\assets\photos\<room>_muse.png` (room = livingroom / masterbed / kitchen ...) + `footage\assets\photos\sources.md` (source file + timestamp, Muse thread, date) |

1. Input = **ORIGINAL material only**: frame stills extracted from `footage\raw\*.mp4` at full 1920x1080
   (`ffmpeg -ss <t> -i footage\raw\<clip>.mp4 -frames:v 1 drafts\muse_test\src\<room>_still_t<t>.png`) and/or the original photos in `footage\raw\photos\`. Never send a previous AI version for another pass.
2. Attach files **one at a time** (multi-attach fails). Send **ONE complete prompt** per send with ALL requirements at once (do not add requirements in follow-up turns). Template, verbatim (fill `<房间名>` and the object list):

       这些是<房间名>的原始素材，请直接从原图各生成一张 AI 优化版，要求一次满足：1. 富士微单 + 35mm 镜头实拍质感（富士色彩、自然透视、微单景深表现）。2. 4K 画质：细节清晰锐利，地板、布料、墙面、家具边缘纹理真实，不要涂抹感和塑料感。3. 光影重塑：阳光明媚，窗外自然光大量涌入，有光线层次和自然光斑阴影。4. 通透：室内整体提亮，暗部和角落不发闷，空气感强，白平衡干净暖白（不偏黄不发灰），高光不过曝，房产宣传片质感。5. 不改构图、不增删任何物品（<逐项列出画面中易被删的物品，如空调、电线、凳子、挂件>全部保留）。按最大原生尺寸输出，只做图片，不要生成视频。

3. **Do NOT remove clutter or objects** (an earlier clutter-removal try deleted the AC). List every easily dropped object in item 5 of the prompt.
4. Size: Muse native max **2096x1184** (16:9). Keep it native: no downscale, no traditional upscale. Muse has no generative super-res and its "3840" versions are plain upscales; "4K" here means texture quality only. The user accepted 2096 (no external 4K step).
5. Download each result via the **lightbox** (open the image, download there; `sandbox://` links do not download), save into `drafts\muse_test\<round>\`.
6. QA before use (all must pass, then copy to `footage\assets\photos\<room>_muse.png` and add a line to `sources.md`):
   - Side-by-side with the original (`drafts\muse_test\cmp\<room>_cmp.jpg`); every object still there, composition unchanged.
   - Window views are AI-redrawn: acceptable, note it in `sources.md`.
   - Brightness really lifted and airy (the bedroom version tended to stay flat/dark): if not, re-send the original with the full prompt and stronger lift wording.
   - No listing IDs, contact info, unit/door numbers, or file names in frame.
7. Video (**experimental, not default; the user has not decided video handling yet**): Muse AI video is image-to-video only (first frame = the enhanced still; no video-to-video), native **1248x704, 24 fps, fixed 10 s**, and it invents details after ~6 s (window view changes, an extra photo frame appears, TV-wall calligraphy turns into a mural); its pan is slower than the original. If used at all: cut before details drift (≤ ~6 s), review every frame, ask the user first.
Reference test: `ep02-zidong`, Muse thread https://muse.ai/thread/cb5b2959-9140-465d-a711-acd025f13664 ; accepted outputs `footage\assets\photos\livingroom_muse.png`, `masterbed_muse.png` (box copies `/workspace/mapkoubo/episodes/ep02-zidong/muse_test/muse_airy/`).
Check: each `footage\assets\photos\*.png` is 2096x1184, listed in `sources.md`, and passed the QA list above.

## 5b. Floor plan (CRM plan -> flova cleanup -> footage\assets\floorplan\)
1. Source: CRM `floor_plan_image_url` of this listing (read-only, docs/crm.md) -> `<EP>\footage\assets\floorplan\floorplan_crm_original.jpg`.
2. flova edit mode (`scripts\flova\mcp_call.py generate_image <req.json>`; gpt-image-2.5-sunburst, 4:3, 2K, count 1, original:true, reference = the CRM plan; trials in `<EP>\out\drafts\floorplan3d\`). Prompt: keep top-down 2D, identical walls/doors/windows/room positions/proportions, keep room labels + areas + north arrow, remove the watermark completely, refined promo colour plan (crisp walls, subtle wood/tile, soft shading, light background). Owner-built additions (e.g. balconies) are NOT drawn; follow the CRM plan exactly.
3. QA with zoom crops: every label/area/number must match the original; any garbled Chinese or number = fail. If dimension numbers garble, drop dimension lines. If labels garble, also make a no-text version and overlay labels in code.
4. Accepted -> `floorplan_clean.png` / `floorplan_clean_notext.png`, transparent cutouts `floorplan_cutout*.png`, and a `README.md` (source, flova request, QA result). No unit/door numbers on screen.

## 5. Muse footage (Playwright MCP, logged-in Muse)
    python pipeline\maphub\make_muse_batches.py <EP> --out <EP>\muse_prompts
- Batches of 4–5 clips; prompt files in `<EP>/muse_prompts/batch_*.md`, targets in `manifest.json` (`footage/shots/<ID>.mp4`).
- Per batch: open Muse in the Playwright browser, paste each prompt, generate, wait, download, save as `<EP>/footage/shots/<ID>.mp4`.
  Image references = listing photos only. Muse avatar/presenter clips are NOT used (HeyGen replaces them).
- Clips: rooms LR/BR/KB (2–3 each), ENV (小区), NB (market/mall/park, generic), MET1 (≈2 s used).
Check: `ffprobe` each clip (≥ 5 s, ≥ 1088×816); look at 3 frames per clip; reject warped text/logos.

## 6. Annotations (scanline-annotate-focus)
Per clip pick 2–4 real, visible objects (generic names: 岩板台面, 嵌入式洗碗机; no brands, no sizes):
    python pipeline\maphub\track_annotations.py grid <EP>\footage\LR1.mp4 --t 1.0     (grid to place boxes)
    # write <EP>\annotations\seeds\LR1.json  {t, targets:[{label, en, box:[x,y,w,h] (0..1), kf?}]}
    python pipeline\maphub\track_annotations.py track <EP>\footage\LR1.mp4 --preview
Check the `_preview.mp4`; hand-key `kf` for drifting low-texture targets or drop them.

## 7. HeyGen avatar (Playwright MCP, logged-in HeyGen)
See also [`RUNBOOK-heygen-avatar.md`](RUNBOOK-heygen-avatar.md) for the avatar/look/generate steps.
- **Look rule (always):** open avatar Cool Breeze, select the user's SAVED look by name (`heygen.look` in presenter.yaml, "Professional in suit on sofa", confirmed by the user 2026-10-13; episode `presenter_override.heygen.look` wins), and verify on screen that this look is selected before Generate. Never use a default/stock look. If the look is not found, STOP and ask the user; do not generate (one credit per episode).
- Create ONE landscape 16:9 720p video with avatar **Cool Breeze**; audio = upload `<EP>/heygen/heygen_audio.wav`
  (lip-sync to our audio — do NOT type the script, do NOT use HeyGen TTS/voices). Plain background, face centred.
- Generate once, download MP4 to `<EP>/heygen/export.mp4`. Do not overwrite this file later.
- **7b. De-watermark + 4:3 (fixed step, before any split or matting).** HeyGen exports 16:9 1280x720 with a HeyGen mark bottom-right; camera, background and presenter position are fixed.
      python pipeline\maphub\heygen_43.py <EP>            (exits 3 at the flova hand-off)
      python scripts\flova\mcp_call.py generate_image <EP>\heygen\dewm\flova_request.json
         (or call flova-image generate_image with that request: gpt-image-2.5-sunburst, 4:3, 2K, original=true, profile kid4, reference = heygen/dewm/canvas.png)
      copy the returned PNG to <EP>\heygen\dewm\plate_43.png
      python pipeline\maphub\heygen_43.py <EP> --qa
  What it does: full-length matte of export.mp4 (scripts/matting, MatAnyone2 -> RVM fallback) -> clean background plate (per-pixel median where the presenter is absent) -> canvas with the plate at the bottom 1440x810 -> flova removes the HeyGen text and outpaints 270 px upward -> plate aligned back with ECC (fit rejected if it drifts) -> presenter (x1.125) composited over it; HeyGen mark pixels on the presenter are Telea-inpainted per frame -> `heygen/export_43.mp4` (1440x1080, original audio).
  Check: `heygen/dewm/qa/before_after.png` shows no HeyGen text and no seam at y=270; `align.json` near identity with ty ~ 270; `composite.json` frames = export frames; duration = export.mp4. Cost ~12 flova credits per episode. Resumable: delete `export_43.mp4` (or pass --force) to rebuild.
  Split then uses `export_43.mp4` automatically. (Legacy `heygen_mark.py` / `export_nomark.mp4` only when 7b is skipped.)
      python pipeline\maphub\heygen_plan.py <EP> split [--offset s] [--sync s] [--dry-run]
  Lip-sync: no lip-sync compensation by default (decided 2026-10-19); apparent desync was from remote-desktop viewing. `--sync` / episode.yaml `heygen_sync` stay available but default to 0; SyncNet check/shift only if the user explicitly asks (CONVENTIONS-shared.md section 3).
Check: export duration = plan total ±0.5 s (else set --offset); lips match the first and last segment. Split with no src uses `export_nomark.mp4` when the mark step is done, or `export.mp4` when it reports absent.
`<EP>/heygen/crop.json` {"HG04": 0.47} to re-centre the 4:3 crop per segment if needed.

## 8. Matting (hook avatar in front of the list)
    scripts\matting\matte_local.cmd <EP>\footage\heygen\HG00.mp4 --downsample 0.4
  After 7b, HG segments and HG00_alpha.webm are native 4:3 1440x1080: Remotion places them 1:1, no crop (footage.json w/h from ffprobe via sync_assets). Re-run this matte whenever HG00 is re-split so the alpha matches. Without 7b, 16:9 1280x720 segments are still centre-cropped around heygen/crop.json cx (fallback).
    copy <EP>\matte\HG00_alpha.webm <EP>\footage\heygen\HG00_alpha.webm
(MatAnyone2 is the local default on the 1070 Ti — same command, same three output files;
it automatically falls back to RobustVideoMatting if MatAnyone2 is unavailable or fails.
Kaggle is the later backup, docs/kaggle-gpu.md.) Check `<EP>/matte/HG00_check.mp4`: hair/shoulders clean.
Hook stacking after this matte is in "User taste rules" below: room plate, then side text and photos, then the alpha, then the caption above the brand strip.

## 9. Assemble
    python pipeline\maphub\stage.py <EP>
    python pipeline\maphub\sync_assets.py <EP>
    cd <EP>\work\remotion; npm run typecheck
    # from the repo root; technical preflight is enforced:
    python pipeline/maphub/render_episode.py <EP> --still 60
    python pipeline/maphub/render_episode.py <EP> --concurrency 4
    # add --draft only for an explicitly marked draft; final QA below still applies
(1070 Ti box: render ≈ 10–20 min for 2 min.)

## 10. QA (all must pass before reporting)
Review stages (CONVENTIONS-shared.md §1a): only **roughcut** (`out\drafts\roughcut_v<N>\<episode>_roughcut_v<N>.mp4` + `notes.md`, SR skipped, rough mix OK; iterate v1, v2...) and **final** (after the user approves the roughcut: `out\release\<episode>_<platform>.mp4`). No animatic / fine-cut.
Output paths follow CONVENTIONS-shared.md §1: test renders -> `out\drafts\vN\`, final platform exports -> `out\release\<episode>_<platform>.mp4`, superseded finals -> `out\archive\`.
`python pipeline/maphub/render_episode.py <EP> --platform douyin|shipinhao` writes `out\release\<episode>_<platform>.mp4`; `--draft --ver vN` and `--still N --ver vN` write `out\drafts\vN\`; `--dry-run` prints the path and command. (ep07's old outputs were moved on 2026-10-19: `out\archive\ep07_koubo_20261010.mp4` + `_v2_` (identical copies), hook tests in `out\drafts\v7_hook\`.)
    ffmpeg -i out\release\<episode>_<platform>.mp4 -af ebur128 -f null -          → Integrated −16 ±0.5 LUFS
    ffmpeg -i out\release\<episode>_<platform>.mp4 -vf freezedetect=n=0.001:d=1.5 -map 0:v -f null -   → no freeze_start
    ffmpeg -i out\release\<episode>_<platform>.mp4 -vf "fps=1/6,scale=480:-1,tile=6x4" -frames:v 1 out\drafts\vN\contact.jpg
Look at the contact sheet + stills at: hook, opener end, each click, END panel:
- Only the bottom brand strip as on-screen note (no AI示意/示例数据/AI数字人/disclaimer chips; `episode.json onScreenNotes:false`).
- Brand strip order 链家, 德佑, 富房, CENTURY 21, 中环, nothing clipped (also in the END panel next to the PiP).
- Occlusion: hook text and photos stay in the side columns and never cover the face, hands, or chest. The spoken caption is a centred pill above the brand strip, not inside the left fact column. PiP never covers captions, pins or the END brand row.
- Opener end: all marks visible, no overlapping labels, title readable; no routes until their POI is narrated.
- Clicks: glide → pause → press + ripple → clip opens; readable at 50 % thumbnail.
- Captions match the voice; on-camera lips in sync (HeyGen).
Report: path, duration, on-camera seconds, LUFS, contact sheet, weaknesses.

### 10A. 标注稳定与指引线 QA（强制）

按 `docs/maphub-execution.md` 的“标注、指引线与模板继承”执行：真实房源不加样板间字样；地图、室内跟踪和 3D 场景的移动文字统一使用固定图像标签；轨迹、播放入点和坐标变换同一时钟；指引线避让所有前景与字幕，绘制在前景下方。先做连续帧标注检查与真实物体附着检查，再导出完整视频。单帧误差、typecheck 或渲染成功均不能替代运动验收。

本次及后续修复必须落在共享模板，stage 后核对新模块与工作副本一致。已导出的旧视频不会自行改变；其他系列只有实际复用组件才继承。新分期仍须逐片做标注与遮挡 QA。

## User taste rules (from ep07 reviews)

### Hook layering (v7) - SUPERSEDED 2026-10-21 by the v8b hook
The v7 rules (headline split around the face, off-white 12 px card borders, cards sliding in from the sides, no-overshoot easing, f58/f66 timing) are retired. The one current hook rule is **"Hook (v8b layout)"** in "租赁房源剪辑规范补充" at the end of this file. Still valid from v7: layer order plate -> title/facts/photos -> matted presenter (HG00_alpha) -> caption pill -> brand strip; without HG00_alpha the presenter is not drawn in front (re-run step 8). QA stills: hook start, each element entrance, hook end.
- Map is the backbone; every section starts and ends on the map. Opener ends on the map with ALL marks already in
  (staggered entrances, collision-avoided labels with leader lines, pins legible at 50 % thumbnail); hub continues with no re-pop.
- Routes draw only when their POI is narrated. Single plain mouse pointer (no name tag), ≈1.7× size.
- Click timing (frames @30): glide 24 (ease in/out) · pause 9 · press 11 (pointer scales down, mark depresses, ripple r≈110 px,
  thick accent ring with white + dark outline) · clip opens after ripple ≥ 70 % · open 18 · close 18 · camera push-in 1.6× before press.
- scanline-annotate-focus used generously, 2–4 objects per clip, each readable.
- Hook: see "Hook (v8b layout)" at the end of this file (layer order in the superseded v7 note above).
- END: avatar small PiP + summary panel (@贝壳-TV, listing highlights, brand logos).
- Presenter full screen only in the hook; otherwise PiP or cut-aways.
- Voice: energetic, natural 口播 (F5), not flat; 影视飓风 rhythm.
- Brand strip only; brands 链家, 德佑, 富房 (full 不动产 box), CENTURY 21, 中环 (red mark + black text).
- Runtime: quality first, not a shorter duration (ep02 rule). Never cut natural pauses inside a take; only trim timeline gaps between lines when they hurt the flow.

## Kaggle queue policy (all Kaggle steps)
Run every Kaggle script with the conda base python `C:\ProgramData\miniconda3\python.exe` (only it has the OAuth login).
Never wait in the queue: `push_job.py --kind sr|tts|matting` polls ~45 s after each push; still QUEUED -> delete the session and re-push, max 10 attempts.
If all 10 stay queued/fail:
- `--kind sr` (SeedVR2 超分, optional, only when the user asks; `--job upscale --kernel seedvr2_v9 --kind sr`): exit 23 = super-res skipped -> **keep the lanczos version and deliver normally**, note it in the report (changed 2026-10-19; it used to stop the pipeline with exit 20).
- `--kind tts` (section 4, `push_indextts25.py` passes it): exit 21 -> automatic local F5 (`clone_tts_f5.cmd`, same narration.json, ref_phone_v1) into `<EP>/voice/f5_fallback_<run>/`; continue with those wavs.
- `--kind matting` / other: exit 22, stop and report.
Details: `docs/kaggle-gpu.md` (排队策略). Dry test: `--dry-run --mock-status queued`.


## Area boundaries (AOI) and gates - added 2026-10-20 (ep02 v6)
Rule: every place the narration introduces (community, mall, school, hospital, metro...) is marked on the map; if its area boundary is obtainable by a documented method, draw it (outline + light fill) when the line first mentions it.
- `map.py aoi "<name>" --city 成都` (or `--id <poiid>`) calls only documented Amap Web Service endpoints and prints: POI id/location, `navi.entr_location`/`exit_location` (v5 place/text `show_fields=navi`), the polygon from `v5/aoi/polyline` (Amap high-tier service: must be enabled by a ticket; until then it returns `INSUFFICIENT_PRIVILEGES 10012`), and `v3 regeo extensions=all` aois (id/name/area only, no polygon).
- Status 2026-10-20: our key lacks the AOI polyline privilege. v3 place/text `extensions=all` has `entr_location` but no shape field; v5 `show_fields` has no shape option. Without a polygon, trace from Amap tiles by hand (say so in notes) or mark the POI pin only.
- Gates: use `entr_location` as an official gate. Gates that are not in the API (for example ep02's north gate, read from tile labels) may be traced; note the source. Measure walking distances from the gate nearest each destination (map.py route --mode walking).
- Template: the community polygon goes in pois.json `aoi` {pts, gate_xy} (drawn after the opener). For any other POI, add `aoi` (plane xy[]) to that entry in pois.json `pois[]`. It is drawn on the first line whose `poi` lists that id (stroke draws on over 1 s, then the fill fades in) and stays after.
- Nearby schools/hospitals: v5 place/around with `types=141203` (小学) / `090100|090101|090102` (综合医院), `sortrule=distance`, from the gate, then a walking route to `entr_location`. Never imply school-district enrolment.

## B-roll montage + hold (ep02 v6)
- A line may set `"hold": s` in script_vN.json. The B-roll stays open s seconds after the last word (no new speech; build_vo writes `hold_f`; the template keeps the segment open). No TTS regen needed.
- A montage clip is cut with ffmpeg xfade (`fade` 0.35 s dissolve, `smoothleft` 0.3 s whip) into one footage/shots/<ID>.mp4 (1440x1080 centre crop, 30 fps). Track annotations per segment (chained ORB homography inside each segment only) and give each target `t0`/`t1` (clip seconds): the box fires no earlier than t0 and fades at t1 (ScanAnnotate).
- Blur passers-by: template-match track + feathered elliptical pixelate/blur (work\v6_blur.py), then check frame grabs.


## Presenter matte sync rule (2026-10-20, ep02 v7)
The matted presenter (<seg>_alpha.webm) must come from the exact current plate segment: same source, in-point, crop and size. A matte left over from an older split freezes or drifts, and that shows as a doubled presenter (ep02 v6 opener: the v2 matte was 6.77 s, the re-split HG00 was 8.07 s).
- `heygen_plan.py split` moves any matte whose sidecar sha256 != the new segment to footage/heygen/stale/ and tells you to re-run `matte_avatar.py`. matte_avatar.py writes `<seg>_alpha.json` (source sha256).
- `python pipeline/maphub/check_matte.py <EP> --qa` checks the sha, frame count, size, and mean RGB diff inside the matte on every frame (<= 12). It writes plate | composite | diff grabs at each segment's start and end to heygen/qa/. `render_episode.py` runs it and refuses to render on a failure. It also deletes build copies of mattes that no longer exist.
- rembg is not installed on the PC; the box has it in /workspace/.venv-rembg. Matte the exact segment bytes there, copy the result back, and run check_matte.

## Presenter budget + PiP lines
- `oncam_budget_s` in episode.yaml (ep02: 59.5; HeyGen free plan < 60 s, one pass). On-camera = hook + PIP/A lines + any line with `"pip": "HGLxx"` (`"pipPos": "br"|"bl"`). Consecutive PiP lines share one card (no dip); skip the 亚朵 insert and the greenery montage. PiP size/position: CONVENTIONS-shared.md "PiP position is fixed" (330x248 bottom-right; `pipPos` is ignored).
- Hook title: one line, never split the community name (v8). The v7 face-gap split (`hookTitleGap`) is retired.

## OSM boundary fallback
`map.py aoi "<name>" --source osm --near <gcj lng,lat>` (or `--id way/<n>`) uses the public Overpass API (own User-Agent, one request), name match, WGS84->GCJ-02. Output: osm_id, vertices, polygon (GCJ-02) and the ODbL attribution. Store the polygon as pois.json `pois[].aoi` (plane xy) with `aoi_source` (osm id + attribution) and `aoi_credit` ("边界 © OpenStreetMap"; shown small, bottom-left, while the map is up). OSM has no polygon for many residential compounds; keep a hand trace for those.

## Top-right badge
Roughcuts use the template default: ONE row, the render's `platform` prop (render_episode default `shipinhao` = 视频号; alias to the `wechat-channels` row in social.json). For the final per-platform export: `render_episode.py <EP> --platform douyin --badge douyin` (input prop `badge`, filtered in components/SocialBadge.tsx).


## v8 conventions (ep02, 2026-10-20)
- **示例房源 / 示例数据 only for simulated data.** A real CRM listing sets `listing.sample_data: false` (episode.yaml) -> `sampleData: false`, `sampleTag: ""` in episode.json. Templates render every sample tag/notice (BrandStrip, END card, opener tag, AI-notes line) only when `sampleData === true`. Never say it in the voice or captions of a real listing.
- **Opener comp cards are real CRM rentals.** Fetch via crm_connector: `map/suggest` (community -> resblock id), `listings/rental/search` with `resblock_ids` (community_keyword is ignored upstream), `map/nearby` (radius 1.5 km, rooms, price band, whole_rent), then `/prospect` REAL 客厅 photo (fallback: list `title_image_url`), downloaded with `.1500x.jpg` + a User-Agent. Raw responses -> `data/crm_nearby.json`; photos -> `sources/crm/comps/<id>.jpg` -> `public/photos_g/crm_*.jpg`. Verdicts must be TRUE against the shown filters (户型不符 / 租金超出); do not show a comp that actually passes every filter. No ids, contacts, agents, stores or unit numbers on cards.
- **No leftward listing swipe in the opener** (the fast vertical listing scroll, 28 f + SFX, stays): `OPENER_SWIPE = false` in components/opener/Opener.tsx keeps the page at rest (scan corners, verdicts, dimming unchanged).
- **Hook title stays one line** (presenter may occlude it). The v7 face-gap split is in HeygenCut.tsx.bak_v7 only.
- **Floorplan lives in the hook collage** (`hub.json hookFloorplan`), no standalone 户型 B-roll.
- **Door/lock shots from photos**: a still push-in (crop math gives an exact per-frame box: annotations/DR1.json). Use the inside of the entrance door so no door number shows.
- **Keyframes-first**: before a full render, bundle once (`npx remotion bundle src/index.ts --out-dir ../build_vN`) and `npx remotion still ../build_vN MapHubHeygen <png> --frame=N`; contact sheet -> out/drafts/roughcut_vN/keyframes/.
- **PowerShell -> python stdin** is ASCII by default (Chinese becomes `??`). Set `$OutputEncoding=[Text.UTF8Encoding]::new($false)` first, or write a .py file. This caused the v7 "?? ? OpenStreetMap" credit.


## Professional real-estate terms (2026-10-20)
Narration, captions, box labels and cards use standard 房产 terms, not plain descriptions of what is visible: 干湿分离 (not 玻璃淋浴隔断), 南北通透, 飘窗, 精装/简装, 客厅开间, 通顶衣柜, 整体橱柜, 双卫, 明厨明卫, 一梯两户, 双线换乘, etc. Use a term only when the footage or CRM data supports it (no 南北通透 without a north–south layout; no 建面/套内 without the area basis). Plain wording stays only where no standard term exists. Still no 最/第一/唯一 and no ——.

## Map data sources and screenshot boundaries (2026-10-20)
- OpenStreetMap is used ONLY for area boundaries (polygons). Everything else (base map tiles, POIs, distances, walking routes, gates) comes from Amap via map.py. If anything on a map uses OSM for something else, switch it to Amap.
- If OSM has no polygon for a needed place (common for residential compounds) and Amap gives none, ask the user to upload a screenshot (e.g. the Amap app showing the boundary and gates). The agent redraws the boundary from it: georeference on at least two Amap POIs visible in the screenshot (e.g. the community pin plus a nearby POI; check that a known gate falls on the redrawn edge), save the screenshot under footage/assets/map/ and the polygon as GCJ-02 GeoJSON (footage/assets/map/<name>_boundary.geojson), then load it with `map.py aoi "<name>" --source manual --file <geojson>` and store it in pois.json `aoi` with the source noted. Gates and distances stay as measured unless the user asks to change them.

## 租赁房源剪辑规范补充 (ep02-zidong lessons, 2026-10-21)
Applies to every rental (租赁) listing episode. Per-episode switches are marked **[ep switch]**.
- **Review stages**: roughcut -> final only; keyframes (one contact sheet) before every full render. Placeholder roughcut before HeyGen exists: `render_episode.py <EP> --draft --presenter-placeholder` (draft only; waives the two HeyGen-sync checks + matte check, logged to `guard_bypass.log`). Placeholder shots play the old HeyGen footage **muted and looped** in sync (no frozen frame, no doubled head) and show **no 数字人占位 tag**.
- **Opener**: real CRM nearby listings only (never 示例房源, no 「示意」 tag). Keep the fast listing scroll (28 f) **with SFX** on each move; no leftward swipe. `hub.json opener.filter` **[ep switch]** turns the filter section on/off.
- **Title**: never split the community name (e.g. 成发紫东阳光).
- **Hook (v8b layout, the one current hook rule)**: Title one line, never split. Layer order as in the v7 note. 客厅 card top-left, 卧室 card top-right, large floor plan (no white border), rent as 综艺花字 (`3000元/月`) + room chip (`3室1厅`) + 精装. Elements enter **one at a time when the narration mentions them**, spring bounce + squash-and-stretch, pop SFX (`pop_soft.wav`, self-generated). Bounce is hook-only.
- **Floor plan**: 2D CRM plan cleaned by flova (watermark removed) -> transparent PNG, labeled + text-free versions; no 3D renders.
- **Motion tempo**: authoritative rule in CONVENTIONS-shared.md "Motion tempo".
- **PiP**: authoritative rule in CONVENTIONS-shared.md "PiP position is fixed".
- **Captions**: authoritative rule in CONVENTIONS-shared.md "字幕规则 (Captions)".
- **Map / transit / surroundings never static** (>~1.5 s still = fail): camera drift, marker pulse, route flow, distance counter, line badges, POI photo cards. Keyword triggers must match whole tokens: `347米` contains `4` and fired the 4号线 badge early.
- **POI photos**: real on-site photos from web search (e.g. Wikimedia Commons); record source, author, license in the episode README; put CC BY-SA credits in the publish description. Boundary and data sources: "Map data sources and screenshot boundaries" above.
- **Multi-clip segments (L13/L14 type)**: `basic-3d-scene`, light warm purple/yellow palette, clips rotating. L02 shows the map only.
- **End card**: discount text (e.g. 独家折扣) in red with ep01's `MarkerUnderline`.
- **Privacy / wording**: blur people only (shop signs stay unless the user decides otherwise) **[ep switch]**; nothing on screen shows a listing ID, contact, unit/door number, agent name or file name. Professional 房产 terms; no 最/第一/唯一; no —— in TTS text.
- **Voice edits**: quality first, not shorter duration; only trim timeline gaps between lines when needed, never natural pauses inside a take.
- **SFX / BGM**: SFX from Mixkit (`vendor\video-shotcraft\assets\audio\`, `ATTRIBUTION.md`) or self-generated with ffmpeg. BGM **[ep switch]** may come from the 剪映 music cache `C:\Users\shipi\AppData\Local\JianyingPro\User Data\Cache\music\` (hashed names; identify by duration with ffprobe + mtime of when the user previewed it), copy to `footage\audio\` with a README noting source and non-commercial use. Level-match to the previous BGM, keep ducking (0.10 under voice / 0.18 in pauses), 1 s fade in, 2 s fade out, master −16 LUFS. ep02 BGM: 剪映「房地产推广」(LuLu_Production).
- **HeyGen**: free plan, <60 s audio, saved look "Professional in suit on sofa"; procedure in `docs\RUNBOOK-heygen-avatar.md`.
- **Cover**: reuse the series template + existing background, change text only; see CONVENTIONS-shared.md §9.
- **QA efficiency**: verify captions/timing/loudness with data on the PC (scripts, ebur128, freezedetect); at most one contact sheet per check; do not ship many frames between machines.
- **Non-commercial**: the ReelEstate project is not for commercial use.

### Changelog
- 2026-10-21 ep02 lessons: v8c kept (one-take hook-to-map and removed filter rejected in v8d); scroll restored + sped 54->28 f with SFX; 「示意」 removed; placeholder loops muted footage; PiP fixed; tempo normalized; static map gaps filled; captions made verbatim with a completeness gate (v8f); 剪映 BGM (v8g); HeyGen runbook + text-only cover added.

