// Resolve effects.json (pipeline/stages/effects.py) onto the rendered shot list.
// Pool rules MUST match pipeline/stages/effects.py::pool_for_shot.
// SPDX-License-Identifier: Apache-2.0
import type { Shot } from "../types";
import type { EffectId, EffectPool, EffectsDoc } from "./types";

export const poolForShot = (shot: Shot, presenterSeen: number): EffectPool => {
  switch (shot.type) {
    case "hook":
      return "opener";
    case "presenter":
      return presenterSeen === 0 ? "opener" : "chapter_title";
    case "broll":
      return shot.location ? "location_map" : "chapter_title";
    case "spec":
      return shot.spec?.variant === "warning" ? "list_checklist" : "data_number";
    case "wall":
      return "comparison";
    case "map":
      return "location_map";
    case "room":
      return "floorplan";
    case "number":
      return "price";
    case "outro":
      return "cta_ending";
    default:
      return "chapter_title";
  }
};

export type ResolvedEffects = { shot: Map<string, EffectId>; transitionIn: Map<string, EffectId> };

/**
 * Exact shot_id matches win (selection was made on this shot list); otherwise the n-th shot of a pool
 * takes the n-th pick of by_pool[pool] (the agent rewrote shots.json after selection). Never repeats.
 */
export const resolveEffects = (shots: Shot[], doc?: EffectsDoc): ResolvedEffects => {
  const out: ResolvedEffects = { shot: new Map(), transitionIn: new Map() };
  if (!doc) return out;
  const ids = new Set(shots.map((s) => s.id));
  const exact = new Map<string, EffectId>();
  for (const s of doc.selections ?? []) if (s.effect_id && ids.has(s.shot_id)) exact.set(s.shot_id, s.effect_id);
  const cursor = new Map<EffectPool, number>();
  const used = new Set<EffectId>();
  let presenters = 0;
  let prev: EffectId | undefined;
  for (const shot of shots) {
    const pool = poolForShot(shot, presenters);
    if (shot.type === "presenter") presenters++;
    let id = exact.get(shot.id);
    if (!id) {
      const list = doc.by_pool?.[pool] ?? [];
      let n = cursor.get(pool) ?? 0;
      while (n < list.length && (used.has(list[n]) || list[n] === prev)) n++;
      id = list[n];
      cursor.set(pool, n + 1);
    }
    if (id && !used.has(id) && id !== prev) {
      out.shot.set(shot.id, id);
      used.add(id);
      prev = id;
    } else {
      prev = undefined;
    }
  }
  const trs = doc.transitions ?? [];
  trs.forEach((t, i) => {
    if (ids.has(t.before_shot)) out.transitionIn.set(t.before_shot, t.effect_id);
    else if (shots.length > 2) out.transitionIn.set(shots[Math.min(shots.length - 1, 2 + i * 3)].id, t.effect_id);
  });
  return out;
};
