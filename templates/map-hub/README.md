# map-hub 口播 template (shared code)

- `remotion/` — Remotion 4.0.529 project (MapHubKoubo, MapHubHeygen = hook + opener + map hub + END panel, Opener).
  `pipeline/maphub/stage.py` prepares `<EP>/work/remotion`; its public and src/episode links point only at that episode. The shared template is code-only and is never switched between episodes.
- `shared/public/{fonts,brands}` — shared across episodes (brands.json order: 链家, 德佑, 富房, CENTURY 21, 中环; see brands/brands.md).
- Pipeline: `pipeline/maphub/*.py`. Rules: `rules/map-hub/`. Runbook: `docs/RUNBOOK-map-hub-koubo.md`.
- Example episode: `projects/listing/ep02-zidong/` (ep07-xihu test episode was deleted 2026-10-25).

## Hook layering
The HeyGen hook (HeygenCut.tsx) puts the huge AlimamaShuHeiTi headline, facts line and bordered photo cards BEHIND the matted presenter and in front of the plate; caption and brand strip stay in front. Full spec: docs/RUNBOOK-map-hub-koubo.md, User taste rules -> Hook layering.
