# Curated effects catalog (real-estate)

Seeded, deterministic effect picks for ReelEstate promos. Each video draws from purpose pools so consecutive cuts stay fresh without random chaos.

## Sources & license

| Source | License | What we use |
|---|---|---|
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | Apache-2.0 | Motion grammar reference; Remotion ports are **re-implemented and re-skinned** to the mediastorm style tokens. Attribution preserved. |
| [video-talkcraft](https://github.com/Vincentwei1021/video-talkcraft) | PolyForm Noncommercial 1.0.0 | 当前实现仅采用语义分类（钩子 / 数据 / 对比 / 列举 / 号召…），未复制其代码、演示或素材；后续按本项目非商业用途规则评估接入，非商业许可本身不构成排除理由。 |

Excluded motifs (too cheesy for property explainers): neon marquees, bubble swarms, paper planes, heavy glitch, confetti bursts, magician flourishes.

## Pools

| Pool | Typical shot | Ported effects (≥2) |
|---|---|---|
| `opener` | first presenter / hook | `blur-slide`, `lead-word-zoom`, `brand-frame` |
| `chapter_title` | room / location title | `marker-underline`, `brace-expand` |
| `data_number` | area / specs as number | `odometer-roll`, `count-up` |
| `comparison` | listing wall / A-vs-B | `before-after-slider`, `dual-stat` |
| `price` | rent / sale price | `price-odometer`, `price-pop` |
| `floorplan` | room + locator | `scan-bracket`, `scanline-focus` |
| `location_map` | map / POI | `pin-callout`, `map-reticle` |
| `transition` | between sections | — (mediastorm is hard-cut only; no transition effects are drawn) |
| `list_checklist` | highlights / drawbacks | `list-reveal`, `checklist-stack` |
| `cta_ending` | outro | `cta-lockup`, `wordmark-settle` |

Full machine-readable list: `catalog.json`.

## Selector

Stage: `pipeline/stages/effects.py` (wired as `effects` in `npm run make`, runs **before** `script`).

- **Seed** = project id (stable on re-render). Pass `--reseed` (or `--answer effects.reseed=N`) to bump the salt and get a new draw.
- **Pool per shot**: presenter#1→opener, later presenter / plain broll→chapter_title, broll+location & map→location_map, wall→comparison, spec→data_number (warning spec→list_checklist), room→floorplan, number→price, outro→cta_ending. mediastorm is hard-cut only (rules/style/mediastorm.md §4), so the transition pool stays empty and no transitions are drawn. Keep `pool_for_shot` (Python) and `poolForShot` (`remotion/src/effects/select.ts`) in sync.
- **Constraints**: no effect twice in one video; adjacent shots differ; max 2 high-energy per 30 s; prefer effects not used in the last 5 videos (`projects/.effects-history.json`, gitignored). Pools with only 2–3 ports can't always avoid history — then a seeded draw weighted to the least-recently used.
- **Determinism**: seed string `"<project_id>::effects::<reseed>"`. Re-running with `--force` only considers history recorded *before* this project, so it re-derives the same picks.
- **Output**: `effects.json` (`by_pool`, `transitions`, per-shot `selections`; `transitions` is empty for mediastorm). `pipeline/render.py` injects it as the `effects` prop; `resolveEffects()` matches by shot id, else by pool order, so it survives the agent rewriting `shots.json`.
- **Replacement**: number/price/checklist/location/CTA effects replace the built-in SpecCard / DataNumber / LocationLabel / OutroCTA for that shot; opener/chapter/comparison/floorplan effects are additive layers.

```powershell
npm run make -- "一句话" --mock                        # effects stage runs automatically before script
npm run effects -- projects/rental/<id> --reseed        # redraw: reseed +1 (then re-render)
npm run effects -- projects/rental/<id> --reseed 7      # a specific salt
npm run effects -- projects/rental/<id> --force         # re-derive (same seed → same picks)
```

## Adding an effect

1. Read the source card + demo TSX in video-shotcraft (Apache-2.0); keep its tuned timing, drop its skin.
2. Implement in `remotion/src/effects/*.tsx` using only `StyleTokens` colours/fonts; add the SPDX + attribution header.
3. Register it in `remotion/src/effects/registry.ts` and `types.ts` (`EffectId`), and add a catalog entry (`ported: true`).
4. 第三方动效代码按本项目非商业用途规则（`AGENTS.md` §1 / `docs/CONVENTIONS-shared.md` §0）评估；不再仅因 talkcraft 使用非商业许可而禁止移植。实际接入仍须满足原许可的署名、修改与再分发条件。

## Remotion

Ports live in `remotion/src/effects/`. They take `StyleTokens` (colors/fonts/motion) — never the original demo skins.

## Layout & taste rules (video-taste)

Every effect follows the shared video-taste skill (`/home/box/agent-data/workflows/video-taste/SKILL.md`):

- **Zones**: `ShotVideo` passes `zones` (caption band y 780–1000, PiP box from the style's `pip` tokens, action-safe 48 px). Readable effect content ends above `CONTENT_BOTTOM` (760) and clears the PiP by 24 px (`bottomLimit()`); openers and the CTA lockup sit in the title-safe top band (≥88 px top / 96 px sides), clear of the presenter's face.
- **One label family**: `chip()` / `card()` (scene-tinted dark material, radius 10 / 14, tinted shadow) for every info label; `slab()` (accent fill, auto off-black/off-white ink via `onColor()`) is the single hero exception.
- **Text hygiene**: `clean()` strips em/en-dash separators; `dotLines()` splits at top-level `·` so each line carries ≤1 middle dot; long strings shrink with `fitFont()` instead of clipping.
- **Colour**: `ink()` = off-white `#FBFBF8` / off-black `#141214` (never pure #fff/#000); shadows tinted with `st.dark`; soft `scrim()` behind light text on footage.
- **Motion**: staggers keep ≤3 units moving (≤5 animators incl. camera); overshoot ≤12 %; no perpetual loops; after settling, blocks drift slowly and un-pushed stills get a ≤2.5 % hold drift so no window is static ≥0.8 s.
