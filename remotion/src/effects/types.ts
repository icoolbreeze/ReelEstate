// Curated effects (rules/effects/catalog.json). Motion grammar adapted from video-shotcraft
// (Apache-2.0, https://github.com/Vincentwei1021/video-shotcraft), re-implemented and re-skinned
// to ReelEstate style tokens. SPDX-License-Identifier: Apache-2.0
import type { StyleTokens } from "../styles/types";
import type { Project, Shot } from "../types";
import type { Zones } from "./kit";

export type EffectPool =
  | "opener"
  | "chapter_title"
  | "data_number"
  | "comparison"
  | "price"
  | "floorplan"
  | "location_map"
  | "transition"
  | "list_checklist"
  | "cta_ending";

export type EffectId =
  | "blur-slide"
  | "lead-word-zoom"
  | "brand-frame"
  | "marker-underline"
  | "brace-expand"
  | "odometer-roll"
  | "count-up"
  | "before-after-slider"
  | "dual-stat"
  | "price-odometer"
  | "price-pop"
  | "scan-bracket"
  | "scanline-focus"
  | "pin-callout"
  | "map-reticle"
  | "clock-wipe"
  | "color-block-wipe"
  | "list-reveal"
  | "checklist-stack"
  | "cta-lockup"
  | "wordmark-settle";

export type EffectSelection = { shot_id: string; type?: string; pool: EffectPool; effect_id: EffectId | null; energy?: string };
export type EffectTransition = { before_shot: string; effect_id: EffectId; energy?: string };

/** Mirrors pipeline/stages/effects.py output (projects/<cat>/<id>/effects.json). */
export type EffectsDoc = {
  schema_version?: number;
  project_id?: string;
  style?: string;
  seed?: string;
  reseed?: number;
  by_pool?: Partial<Record<EffectPool, EffectId[]>>;
  transitions?: EffectTransition[];
  selections?: EffectSelection[];
};

/** zones = caption band + PiP box + action-safe rect; effects must keep readable content out of caption/PiP. */
export type EffectProps = { st: StyleTokens; project: Project; shot: Shot; duration: number; zones: Zones };
export type TransitionProps = { st: StyleTokens; duration: number };

/** Which built-in shot component an effect replaces (the rest are additive layers). */
export type Replaces = "none" | "spec" | "number" | "location" | "outro";
