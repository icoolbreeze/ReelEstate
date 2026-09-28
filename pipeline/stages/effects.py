"""Stage: curated seeded effect selection -> effects.json.

Runs BEFORE script (and therefore before render). Seed = project id, so re-renders
are deterministic; `--reseed` bumps a salt to draw again.

Because the agent may rewrite shots.json after this stage, effects.json stores
picks per *pool* in order (`by_pool`) plus transitions; the renderer maps each
shot to a pool (same rules as `pool_for_shot` below / remotion/src/effects/select.ts)
and takes the n-th pick of that pool. `selections` is the per-shot plan for the
shot list known at selection time (shots.json if present, else the fallback layout).

Constraints:
  * no effect twice in one video (per-pool picks never repeat; pools are disjoint)
  * adjacent shots never share an effect
  * at most MAX_HIGH_PER_30S high-energy effects per 30 s of video
  * prefer effects NOT used in the last HISTORY_KEEP videos (projects/.effects-history.json, gitignored);
    when a pool is too small to avoid them all, pick the least-recently used.
"""
from __future__ import annotations

import hashlib
import random
from pathlib import Path

from .common import REPO_ROOT, load_brief, load_json, now_iso, save_json

CATALOG_PATH = REPO_ROOT / "rules" / "effects" / "catalog.json"
HISTORY_PATH = REPO_ROOT / "projects" / ".effects-history.json"
HISTORY_KEEP = 5
MAX_HIGH_PER_30S = 2
SECONDS_PER_SHOT = 3.2  # fallback estimate when narration durations are unknown

POOL_BY_TYPE = {
    "wall": "comparison",
    "map": "location_map",
    "room": "floorplan",
    "number": "price",
    "outro": "cta_ending",
}


def pool_for_shot(shot: dict, presenter_seen: int) -> str:
    """Keep in sync with remotion/src/effects/select.ts (poolForShot)."""
    t = shot.get("type") or "broll"
    if t == "presenter":
        return "opener" if presenter_seen == 0 else "chapter_title"
    if t == "broll":
        return "location_map" if shot.get("location") else "chapter_title"
    if t == "spec":
        return "list_checklist" if (shot.get("spec") or {}).get("variant") == "warning" else "data_number"
    return POOL_BY_TYPE.get(t, "chapter_title")


def load_catalog() -> dict:
    return load_json(CATALOG_PATH)


def _rank(e: dict) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(e.get("energy", "medium")).lower(), 1)


def seed_string(project_id: str, reseed: int) -> str:
    return f"{project_id}::effects::{reseed}"


def _rng(project_id: str, reseed: int) -> random.Random:
    return random.Random(int(hashlib.sha256(seed_string(project_id, reseed).encode("utf-8")).hexdigest()[:16], 16))


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return list(load_json(HISTORY_PATH).get("videos") or [])
    except Exception:
        return []


def _save_history(videos: list[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_json(HISTORY_PATH, {"updated_at": now_iso(), "keep": HISTORY_KEEP, "videos": videos[-HISTORY_KEEP * 4:]})


def _recency(history: list[dict], project_id: str) -> dict[str, int]:
    """effect_id -> how many videos ago it was last used (1 = previous video). Only last HISTORY_KEEP.

    If this project is already in the history, only videos made BEFORE it count, so re-running
    the stage (e.g. --force after the agent rewrote shots) stays deterministic.
    """
    ids = [v.get("project_id") for v in history]
    if project_id in ids:
        history = history[: ids.index(project_id)]
    vids = [v for v in history if v.get("project_id") != project_id][-HISTORY_KEEP:]
    out: dict[str, int] = {}
    for age, v in enumerate(reversed(vids), start=1):
        for eid in v.get("effect_ids") or []:
            out.setdefault(eid, age)
    return out


def _pool_effects(catalog: dict, pool: str, style: str) -> list[dict]:
    return [
        e for e in catalog.get("effects") or []
        if e.get("pool") == pool and e.get("ported", True) and (not style or style in (e.get("styles") or [style]))
    ]


def _choose(rng: random.Random, cands: list[dict], recency: dict[str, int], high_left: int, prev: str | None) -> dict | None:
    cands = [e for e in cands if e["id"] != prev]
    if not cands:
        return None
    if high_left <= 0 and any(_rank(e) < 2 for e in cands):
        cands = [e for e in cands if _rank(e) < 2]
    fresh = [e for e in cands if e["id"] not in recency]
    if fresh:
        return rng.choice(fresh)
    # All used recently: seeded draw weighted toward the least-recently used (older = likelier).
    weights = [recency[e["id"]] ** 2 for e in cands]
    return rng.choices(cands, weights=weights, k=1)[0]


def select_effects(project_id: str, style: str, shots: list[dict], *, reseed: int = 0,
                   history: list[dict] | None = None, video_seconds: float | None = None) -> dict:
    catalog = load_catalog()
    rng = _rng(project_id, reseed)
    recency = _recency(history if history is not None else load_history(), project_id)
    secs = video_seconds or max(15.0, len(shots) * SECONDS_PER_SHOT)
    high_left = max(1, round(MAX_HIGH_PER_30S * secs / 30.0))

    remaining: dict[str, list[dict]] = {}
    by_pool: dict[str, list[str]] = {}
    selections: list[dict] = []
    used: set[str] = set()
    prev: str | None = None
    presenter_seen = 0

    for shot in shots:
        pool = pool_for_shot(shot, presenter_seen)
        if shot.get("type") == "presenter":
            presenter_seen += 1
        if pool not in remaining:
            remaining[pool] = _pool_effects(catalog, pool, style)
        cands = [e for e in remaining[pool] if e["id"] not in used]
        choice = _choose(rng, cands, recency, high_left, prev)
        if choice is None:
            # Pool exhausted: leave the shot on its built-in look rather than repeating an effect.
            selections.append({"shot_id": shot.get("id"), "type": shot.get("type"), "pool": pool, "effect_id": None})
            prev = None
            continue
        used.add(choice["id"])
        if _rank(choice) >= 2:
            high_left -= 1
        by_pool.setdefault(pool, []).append(choice["id"])
        selections.append({"shot_id": shot.get("id"), "type": shot.get("type"), "pool": pool,
                           "effect_id": choice["id"], "energy": choice.get("energy")})
        prev = choice["id"]

    # Transitions: an accent wipe at up to len(pool) segment boundaries (no repeats).
    tr_cands = [e for e in _pool_effects(catalog, "transition", style)]
    rng.shuffle(tr_cands)
    tr_cands.sort(key=lambda e: (e["id"] in recency, -recency.get(e["id"], 99)))
    transitions: list[dict] = []
    boundaries = [i for i in range(1, len(shots)) if shots[i].get("segment") and shots[i].get("segment") != shots[i - 1].get("segment")]
    if not boundaries:
        boundaries = list(range(2, len(shots), 3))
    rng.shuffle(boundaries)
    for e in tr_cands:
        if not boundaries:
            break
        if _rank(e) >= 2 and high_left <= 0:
            continue
        b = boundaries.pop()
        if _rank(e) >= 2:
            high_left -= 1
        transitions.append({"before_shot": shots[b].get("id"), "effect_id": e["id"], "energy": e.get("energy")})
        used.add(e["id"])
    transitions.sort(key=lambda t: [s.get("id") for s in shots].index(t["before_shot"]))

    return {
        "schema_version": 1,
        "project_id": project_id,
        "style": style,
        "seed": seed_string(project_id, reseed),
        "reseed": reseed,
        "generated_at": now_iso(),
        "generated_by": "pipeline/stages/effects.py",
        "catalog": "rules/effects/catalog.json",
        "constraints": {"unique": True, "adjacent_differ": True, "max_high_per_30s": MAX_HIGH_PER_30S,
                        "avoid_last_videos": HISTORY_KEEP},
        "by_pool": by_pool,
        "transitions": transitions,
        "selections": selections,
    }


# Mirrors pipeline/stages/script_stage.py build_shots() so picks line up with the fallback script.
FALLBACK_SHOTS = [
    {"id": "sh01", "segment": "s01", "type": "presenter"},
    {"id": "sh02", "segment": "s01", "type": "wall"},
    {"id": "sh03", "segment": "s02", "type": "broll", "location": {"main": "-"}},
    {"id": "sh04", "segment": "s02", "type": "spec", "spec": {"title": "-", "lines": []}},
    {"id": "sh05", "segment": "s03", "type": "room"},
    {"id": "sh06", "segment": "s03", "type": "room"},
    {"id": "sh07", "segment": "s04", "type": "number"},
    {"id": "sh08", "segment": "s04", "type": "spec", "spec": {"title": "-", "lines": [], "variant": "warning"}},
    {"id": "sh09", "segment": "s05", "type": "map", "location": {"main": "-"}},
    {"id": "sh10", "segment": "s05", "type": "outro"},
]


def run(project_dir: Path, force: bool = False, reseed: int | None = None) -> dict:
    out = project_dir / "effects.json"
    brief = load_brief(project_dir)
    project_id = brief.get("project_id") or project_dir.name
    style = brief.get("style") or "mediastorm"
    existing = load_json(out) if out.exists() else {}

    if reseed is None and out.exists() and not force:
        return {"skipped": True, "seed": existing.get("seed"), "picked": _summary(existing)}

    if reseed is None:
        reseed = int((brief.get("answers") or {}).get("effects.reseed") or existing.get("reseed") or 0)
    elif reseed < 0:  # --reseed without a value: bump
        reseed = int(existing.get("reseed") or 0) + 1

    shots_p = project_dir / "shots.json"
    shots = list(load_json(shots_p).get("shots") or []) if shots_p.exists() else FALLBACK_SHOTS
    doc = select_effects(project_id, style, shots, reseed=reseed)
    save_json(out, doc)

    entry = {"project_id": project_id, "at": now_iso(), "seed": doc["seed"],
             "effect_ids": [s["effect_id"] for s in doc["selections"] if s.get("effect_id")]
             + [t["effect_id"] for t in doc["transitions"]]}
    hist = load_history()
    ids = [v.get("project_id") for v in hist]
    if project_id in ids:
        hist[ids.index(project_id)] = entry  # keep its place so older/newer ordering is preserved
    else:
        hist.append(entry)
    _save_history(hist)
    return {"seed": doc["seed"], "reseed": reseed, "picked": _summary(doc)}


def _summary(doc: dict) -> str:
    parts = [f"{s['pool']}={s['effect_id']}" for s in doc.get("selections") or [] if s.get("effect_id")]
    parts += [f"transition={t['effect_id']}" for t in doc.get("transitions") or []]
    return ", ".join(parts)
