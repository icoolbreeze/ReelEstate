# RUNBOOK — map-hub 口播 series (end to end, for the local grok agent)

Series: @贝壳-TV map-hub 口播. 1440×1080, 30 fps, −16 LUFS. A satellite-style map is the hub: listing pin, 样板间 room cards,
小区环境, POI pins; a cursor clicks a mark → the clip opens out of it → back to the map. HeyGen avatar ("Cool Breeze") on camera
(hook full screen, then PiP), cloned voice for everything.

Code: `templates/map-hub/remotion` (Remotion) + `pipeline/maphub/*.py`. Rules: `rules/map-hub/`. Example: `projects/map-hub/ep07-xihu`.
All commands run from the repo root `C:\Users\shipi\vswp\ReelEstate` in PowerShell. `<EP>` = `projects\map-hub\epNN-<slug>`.

One series, many episodes. Each episode has its own folder. Voice-clone references, the Cool Breeze profile, fonts, and brand logos stay shared and are not copied in.

| | Path |
|---|---|
| This episode's footage, voice wavs, HeyGen export, matte, map, script, output | `projects/map-hub/<ep>/` |
| Folder name | `ep08-xihu`, `ep12-xihu`, `ep10-yuedu`. Category and layout stay in `episode.yaml` |
| CRM listing id | `<ep>/episode.yaml` `listing.ref` and `<ep>/data/listing_ref.json` only |
| Chinese community name | `episode.yaml` `listing.community` |
| Voice reference | `assets/presenter/cool-breeze/voice/ref_phone_v1.wav` + `ref_phone_v1.txt` (default, also the IndexTTS emotion ref). Fallback: `voices/clone/reference.wav` + `reference.txt` (old HeyGen, read-only) |
| Presenter | `assets/presenter/cool-breeze/presenter.yaml` |
| Fonts and brands | `templates/map-hub/shared/public/{fonts,brands}` |

Categories: `rental` 租赁, `resale` 二手房, `new-home` 新房, `knowledge` 房源知识与市场分析. The user does not create folders. They give a listing id, or a new-home 楼盘 name, and the agent runs section 0. Rental and resale store that id. New-home has no listing id. Knowledge uses a topic. `ep07-xihu` keeps its original folder name. The cloud listing API currently answers rental only.

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
  Listing is 示例数据 unless the user says it is a live listing (then follow rules/compliance).

## Shared resources
- Presenter profile `assets/presenter/<name>/presenter.yaml` (default `cool-breeze`): HeyGen avatar/look/audio-upload rule, voice
  engine + ref wav/text + seed/speeds + Whisper threshold, Muse avatar ref, matting settings. Resolve settings as
  presenter.yaml, then episode.yaml `presenter_override`. Media in `media/` (gitignored); voice refs read-only.
- Fonts/brands: `templates/map-hub/shared/public/` (shared, linked by stage.py).

## 0. New episode (fixed workflow)
    scripts\new_episode.cmd --category rental --slug xihu --listing <id> --title 小区名 [--footage <dir>]
    scripts\new_episode.cmd --category new-home --slug xipai --title 楼盘名
    scripts\new_episode.cmd --category knowledge --slug yuedu --topic 选题
The agent picks the next episode number when `--episode` is omitted. Creates `<EP>/episode.yaml`, `episode.json` (sample numbers cleared), `footage/raw/`, `consent/`, plus `data/listing_ref.json` (rental/resale), `data/project.json` (new-home, no listing id), or `data/topic.json`. Footage rules: docs/FOOTAGE-SPEC.md.
A listing id never goes in the folder name or in `episode.json`. New-home has no listing id. Stage 1 reads `listing.ref` for rental and fills facts from BeikeMicroservice.
Then say `做视频 <id>` to grok, or `scripts\make-video.cmd <id> [stage]` (detached, resumable, logs in `<EP>/jobs/`).
Do not copy `ep07-xihu` by hand. `python pipeline\maphub\stage.py <EP>` prepares this episode's isolated Remotion workspace.
Check: `<EP>/work/remotion/public` and `src/episode` point only into `<EP>`. Shared template links are left untouched.

## 1. Listing data (BeikeMicroservice crm_connector)
- Follow `docs/crm.md` (service on 127.0.0.1:8020; `npm run listing:fetch -- <project>` / `pipeline/stages/listing.py`).
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
- Map order: OPENER → hub intro (PIP) → 样板间 rooms (click each card) → 小区环境 → 周边 (metro, schools, market, mall, hospital, park)
  → summary → END panel (PiP + list + brands) → sign-off "我是贝壳TV，我们下期见".
- On camera: hook + ~6–7 PiP lines; on-camera speech + 0.5 s gaps ≤ 55 s (measured after voice, step 4).
- Spoken compliance: say 示例房源 once; generic B-roll (park/market) → "画面仅作示意".
Check: `python pipeline\maphub\build_vo.py <EP> --script script_vN.json` (edge-tts estimate) prints total ≈ 90–130 s.

## 4. Voice clone (IndexTTS-2.5 on one Kaggle T4)
Engine/seed/speeds from the presenter profile (IndexTTS-2.5, seed 22, 1.05 on-camera / 1.0 VO; CosyVoice rejected as flat). `scripts\voice\push_indextts25.py`, docs `docs/kaggle-gpu.md`. F5 (`scripts\voice\clone_tts_f5.cmd`) only when explicitly requested. edge-tts in section 3 stays the timing estimate.
- Write `<EP>/voice/narration.json` {engine:"indextts25", ref_wav:"assets/presenter/cool-breeze/voice/ref_phone_v1.wav", ref_text:"assets/presenter/cool-breeze/voice/ref_phone_v1.txt",
  lines:[{id, text, seed, speed, emo_ref:"ref_phone_v1.wav", emo_alpha:1.0}]}; one entry per hook + line (or 2-3 large sections; whole passages give the most natural prosody);
- Pauses come from punctuation and line breaks only. Never use `——` (it is read aloud); use `，` or `……`. See docs/voice-style-mediastorm.md.
  text = tts with rhythm punctuation. Flat `text` only.
- Speed 1.0–1.1 still means faster when greater than 1. The kernel converts `duration_factor = 1/speed`. No post time-stretch unless the on-camera budget forces it (then atempo ≤ 1.1).
- For HOOK and on-camera lines generate 2–3 seeds; pick by ear / Whisper score. T4 runs fp32.
      python scripts\voice\push_indextts25.py --episode <EP> --script <EP>\voice\narration.json
      python scripts\kaggle\pull_job.py --episode <EP> --job tts --run indextts25
- Wavs land in `<EP>/kaggle/tts/indextts25/output/out/<id>.wav` (22050 Hz) plus `manifest.json`.
- Post: trim silence, loudnorm −16 LUFS → `<EP>/voice/final/<id>.wav` (ffmpeg `silenceremove…,loudnorm=I=-16:TP=-1.5:LRA=7`).
- Whisper check (`pipeline/asr` or the cosyvoice venv's whisper): similarity ≥ 0.85 per line, otherwise re-roll the seed.
      python pipeline\maphub\build_vo.py <EP> --script script_vN.json --voice-dir <EP>\voice\final
      python pipeline\maphub\heygen_plan.py <EP> plan
Check: heygen_plan prints "HeyGen video ≤ 55 s"; `<EP>/heygen/heygen_audio.wav` + `heygen_segments.md` exist.

## 5. Muse footage (Playwright MCP, logged-in Muse)
    python pipeline\maphub\make_muse_batches.py <EP> --out <EP>\muse_prompts
- Batches of 4–5 clips; prompt files in `<EP>/muse_prompts/batch_*.md`, targets in `manifest.json` (`footage/<ID>.mp4`).
- Per batch: open Muse in the Playwright browser, paste each prompt, generate, wait, download, save as `<EP>/footage/<ID>.mp4`.
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
      python pipeline\maphub\heygen_plan.py <EP> split [--offset s]
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
    ffmpeg -i out\final_vN.mp4 -af ebur128 -f null -          → Integrated −16 ±0.5 LUFS
    ffmpeg -i out\final_vN.mp4 -vf freezedetect=n=0.001:d=1.5 -map 0:v -f null -   → no freeze_start
    ffmpeg -i out\final_vN.mp4 -vf "fps=1/6,scale=480:-1,tile=6x4" -frames:v 1 out\final_vN_contact.jpg
Look at the contact sheet + stills at: hook, opener end, each click, END panel:
- Only the bottom brand strip as on-screen note (no AI示意/示例数据/AI数字人/disclaimer chips; `episode.json onScreenNotes:false`).
- Brand strip order 链家, 德佑, 富房, CENTURY 21, 中环, nothing clipped (also in the END panel next to the PiP).
- Occlusion: hook text and photos stay in the side columns and never cover the face, hands, or chest. The spoken caption is a centred pill above the brand strip, not inside the left fact column. PiP never covers captions, pins or the END brand row.
- Opener end: all marks visible, no overlapping labels, title readable; no routes until their POI is narrated.
- Clicks: glide → pause → press + ripple → clip opens; readable at 50 % thumbnail.
- Captions match the voice; on-camera lips in sync (HeyGen).
Report: path, duration, on-camera seconds, LUFS, contact sheet, weaknesses.

## User taste rules (from ep07 reviews)

### Hook layering (bold, v7; `templates/map-hub/remotion/src/HeygenCut.tsx` HookShot, applies to every episode)
Back to front: 1 HeyGen plate (native 4:3 after 7b) -> 2 headline -> 3 facts line + photo cards -> 4 presenter alpha (HG00_alpha) -> 5 caption pill -> 6 brand strip (unchanged).
- Headline: community name, AlimamaShuHeiTi (`TITLE`), ~230 px (`min(260, 1360/chars)`), centred, top 262 so the presenter's head covers part of it. The occlusion is intended: type and cards always sit BEHIND the matted presenter and IN FRONT of the plate.
- Facts line under the headline, left: rent in the gold accent + layout + area, 54/34 px, tabular-nums.
- Photo cards (max 2): off-white `#FBFAF7` 12 px border, tinted shadow `rgba(38,32,24,.30)`, tilt -3 / +3.5 deg, label tag (room name) bottom-left; slide in from the sides. They may sit behind the presenter, never in the caption band centre.
- Motion (video-taste section 7): entries `Easing.bezier(.16,1,.3,1)`, headline per-char rise 12 f with a 2 f stagger, facts 12 f, cards 10 f at f58/f66; headline drift 1.00 -> 1.03 over the hook; <=5 elements entering at once; no overshoot.
- Caption pill and brand strip stay in front of the presenter and unchanged. Needs HG00_alpha.webm; without it the presenter is not drawn in front (re-run the step 8 matte).
- QA: stills at f12, f40, f80, f140 plus a 5 s clip (`--frames=0-149`); check the head covers the headline only partly and the name stays readable.
- Map is the backbone; every section starts and ends on the map. Opener ends on the map with ALL marks already in
  (staggered entrances, collision-avoided labels with leader lines, pins legible at 50 % thumbnail); hub continues with no re-pop.
- Routes draw only when their POI is narrated. Single plain mouse pointer (no name tag), ≈1.7× size.
- Click timing (frames @30): glide 24 (ease in/out) · pause 9 · press 11 (pointer scales down, mark depresses, ripple r≈110 px,
  thick accent ring with white + dark outline) · clip opens after ripple ≥ 70 % · open 18 · close 18 · camera push-in 1.6× before press.
- scanline-annotate-focus used generously, 2–4 objects per clip, each readable.
- Hook, back to front:
  1. Background is the unmatted HeyGen clip: the host's own room. Do not use the map, and do not lay a flat colour plate behind the person.
  2. Title, the three fact rows, and the room photos on the right sit behind the matte, in the side columns. They must not cover the face, hands, or chest. If there is no alpha, do not place those graphics on the body.
  3. The matted person (`HG00_alpha`) is in front.
  4. The spoken caption is one centred pill above the brand strip. Do not put it in the left fact column.
  No fancy cards over the person.
- END: avatar small PiP + summary panel (@贝壳-TV, listing highlights, brand logos).
- Presenter full screen only in the hook; otherwise PiP or cut-aways.
- Voice: energetic, natural 口播 (F5), not flat; 影视飓风 rhythm.
- Brand strip only; brands 链家, 德佑, 富房 (full 不动产 box), CENTURY 21, 中环 (red mark + black text).
- Keep runtime tight (target ≤ ~95 s when the voice pace allows); trim pauses before trimming content.
