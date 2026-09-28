// Effect id → component + which built-in shot element it replaces.
// SPDX-License-Identifier: Apache-2.0
import type React from "react";
import { BeforeAfterSlider, DualStat } from "./compare";
import { ChecklistStack, CtaLockup, ListReveal, WordmarkSettle } from "./lists";
import { CountUp, OdometerRoll, PriceOdometer, PricePop } from "./numbers";
import { MapReticle, PinCallout, ScanBracket, ScanlineFocus } from "./spatial";
import { BlurSlide, BraceExpand, BrandFrame, LeadWordZoom, MarkerUnderline } from "./titles";
import { ClockWipe, ColorBlockWipe } from "./transitions";
import type { EffectId, EffectProps, Replaces, TransitionProps } from "./types";

type Entry = { kind: "shot"; component: React.FC<EffectProps>; replaces: Replaces } | { kind: "transition"; component: React.FC<TransitionProps> };

export const EFFECTS: Record<EffectId, Entry> = {
  "blur-slide": { kind: "shot", component: BlurSlide, replaces: "none" },
  "lead-word-zoom": { kind: "shot", component: LeadWordZoom, replaces: "none" },
  "brand-frame": { kind: "shot", component: BrandFrame, replaces: "none" },
  "marker-underline": { kind: "shot", component: MarkerUnderline, replaces: "none" },
  "brace-expand": { kind: "shot", component: BraceExpand, replaces: "none" },
  "odometer-roll": { kind: "shot", component: OdometerRoll, replaces: "spec" },
  "count-up": { kind: "shot", component: CountUp, replaces: "spec" },
  "before-after-slider": { kind: "shot", component: BeforeAfterSlider, replaces: "none" },
  "dual-stat": { kind: "shot", component: DualStat, replaces: "none" },
  "price-odometer": { kind: "shot", component: PriceOdometer, replaces: "number" },
  "price-pop": { kind: "shot", component: PricePop, replaces: "number" },
  "scan-bracket": { kind: "shot", component: ScanBracket, replaces: "none" },
  "scanline-focus": { kind: "shot", component: ScanlineFocus, replaces: "none" },
  "pin-callout": { kind: "shot", component: PinCallout, replaces: "location" },
  "map-reticle": { kind: "shot", component: MapReticle, replaces: "location" },
  "clock-wipe": { kind: "transition", component: ClockWipe },
  "color-block-wipe": { kind: "transition", component: ColorBlockWipe },
  "list-reveal": { kind: "shot", component: ListReveal, replaces: "spec" },
  "checklist-stack": { kind: "shot", component: ChecklistStack, replaces: "spec" },
  "cta-lockup": { kind: "shot", component: CtaLockup, replaces: "outro" },
  "wordmark-settle": { kind: "shot", component: WordmarkSettle, replaces: "outro" },
};
