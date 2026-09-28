// Small frame-driven helpers for src/effects (self-contained on purpose).
// SPDX-License-Identifier: Apache-2.0
import type { Project, Shot } from "../types";

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const lerp = (t: number, a: number, b: number) => a + (b - a) * t;
export const ease = {
  linear: (t: number) => t,
  outCubic: (t: number) => 1 - Math.pow(1 - t, 3),
  outQuart: (t: number) => 1 - Math.pow(1 - t, 4),
  outExpo: (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  inOutCubic: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  outBack: (t: number, s = 1.70158) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2),
};
/** 0→1 progress over [f0, f1] through an easing curve. */
export const prog = (frame: number, f0: number, f1: number, fn: (t: number) => number = ease.linear) =>
  fn(clamp01((frame - f0) / Math.max(1, f1 - f0)));

/** "#RRGGBB" + alpha → rgba(). Falls back to the input for non-hex colours. */
export const alpha = (hex: string, a: number): string => {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

/** Deterministic PRNG (mulberry32) so jitter is identical on every render. */
export const rand = (seed: number) => () => {
  let t = (seed += 0x6d2b79f5);
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

// ---- text sources (facts only; never invent market claims) ----
export const titleOf = (p: Project): string => p.property.location.community || p.title;
export const subOf = (p: Project): string =>
  [p.property.layout, p.property.area?.value ? `${p.property.area.value}㎡` : "", p.property.orientation].filter(Boolean).join(" · ");
export const priceOf = (p: Project, shot?: Shot): { value: string; unit: string; caption?: string } => {
  if (shot?.number) return { value: shot.number.value, unit: shot.number.unit ?? p.price.unit, caption: shot.number.caption };
  return { value: p.price.value.toLocaleString("en-US"), unit: p.price.unit };
};
/** Split "4,800" / "68 m²" into its leading number and the rest. */
export const splitNumber = (s: string): { num: string; rest: string } => {
  const m = /^([\d.,]+)(.*)$/.exec(s.trim());
  return m ? { num: m[1], rest: m[2].trim() } : { num: "", rest: s };
};
