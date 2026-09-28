// Small frame-driven helpers for src/effects (self-contained on purpose).
// SPDX-License-Identifier: Apache-2.0
import type { CSSProperties } from "react";
import type { StyleTokens } from "../styles/types";
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
export const titleOf = (p: Project): string => clean(p.property.location.community || p.title);
/** Sub-title facts as separate parts; render them with spacing (never a chain of middle dots). */
export const subParts = (p: Project): string[] =>
  [p.property.layout, p.property.area?.value ? `${p.property.area.value}㎡` : "", p.property.orientation].filter((x): x is string => Boolean(x)).map(clean);
export const priceOf = (p: Project, shot?: Shot): { value: string; unit: string; caption?: string } => {
  if (shot?.number) return { value: shot.number.value, unit: shot.number.unit ?? p.price.unit, caption: shot.number.caption };
  return { value: p.price.value.toLocaleString("en-US"), unit: p.price.unit };
};
/** Split "4,800" / "68 m²" into its leading number and the rest. */
export const splitNumber = (s: string): { num: string; rest: string } => {
  const m = /^([\d.,]+)(.*)$/.exec(s.trim());
  return m ? { num: m[1], rest: m[2].trim() } : { num: "", rest: s };
};

// ---------------------------------------------------------------------------
// video-taste rules (/home/box/agent-data/workflows/video-taste/SKILL.md), shared by every effect.
// ---------------------------------------------------------------------------

export const CANVAS = { W: 1440, H: 1080 };
/** Action-safe inset: every readable element stays ≥48 px from each edge. */
export const SAFE = 48;
/** Caption band (y 780-1000): nothing readable from an effect may enter it. */
export const CAPTION_TOP = 780;
/** Effects keep their readable content above this line (caption band minus breathing room). */
export const CONTENT_BOTTOM = CAPTION_TOP - 20;

export type Rect = { x: number; y: number; w: number; h: number };
/** Layout zones an effect must yield to (computed per shot by ShotVideo). */
export type Zones = { caption: Rect; pip?: Rect; safe: Rect };

export const zonesFor = (st: StyleTokens, pip?: "pip-left" | "pip-right"): Zones => {
  const p = st.pip;
  const pipRect = pip ? { x: pip === "pip-left" ? p.margin : CANVAS.W - p.margin - p.w, y: CANVAS.H - p.bottom - p.h, w: p.w, h: p.h } : undefined;
  return {
    caption: { x: 0, y: CAPTION_TOP, w: CANVAS.W, h: 1000 - CAPTION_TOP },
    pip: pipRect,
    safe: { x: SAFE, y: SAFE, w: CANVAS.W - 2 * SAFE, h: CANVAS.H - 2 * SAFE },
  };
};

/** Lowest y readable content may reach in the horizontal span [x0, x1] (caption band + PiP clearance 24 px). */
export const bottomLimit = (z: Zones, x0: number, x1: number): number => {
  let lim = CONTENT_BOTTOM;
  if (z.pip && x1 > z.pip.x - 24 && x0 < z.pip.x + z.pip.w + 24) lim = Math.min(lim, z.pip.y - 24);
  return lim;
};

/** Off-white / off-black: never pure #fff / #000 on screen. */
export const OFF_WHITE = "#FBFBF8";
export const OFF_BLACK = "#141214";
export const ink = (st: StyleTokens): string => (/^#fff(fff)?$/i.test(st.text) ? OFF_WHITE : st.text);
/** Scene-tinted shadow (never rgba(0,0,0,x)). */
export const shade = (st: StyleTokens, a = 0.35, blur = 18, dy = 6): string => `0 ${dy}px ${blur}px ${alpha(st.dark, a)}`;

/** ONE label family: every info chip/card shares material, radius and shadow. Accent slab is the single hero exception. */
export const RADIUS = { card: 14, chip: 10 };
export const card = (st: StyleTokens): CSSProperties => ({ background: alpha(st.dark, 0.82), borderRadius: RADIUS.card, boxShadow: shade(st, 0.3) });
export const chip = (st: StyleTokens): CSSProperties => ({ background: alpha(st.dark, 0.82), borderRadius: RADIUS.chip, boxShadow: shade(st, 0.25, 12, 4), padding: "4px 14px", whiteSpace: "nowrap" });
export const slab = (st: StyleTokens): CSSProperties => ({ background: st.accent, color: onColor(st.accent), borderRadius: RADIUS.chip, padding: "4px 16px", whiteSpace: "nowrap" });

/** Soft scene-tinted scrim behind a text block so light ink reads on bright footage (contrast ≥3:1). */
export const scrim = (st: StyleTokens, a = 0.55): CSSProperties => ({ background: `radial-gradient(closest-side, ${alpha(st.dark, a)}, ${alpha(st.dark, 0)})` });

/** On-screen text hygiene: no em/en-dash separators, ≤1 middle dot per line. */
export const clean = (s: string): string => s.replace(/\s*[—–]+\s*/g, " ").replace(/\s{2,}/g, " ").trim();
/** Split at top-level " · " (not inside brackets) into lines that each carry ≤1 middle dot. */
export const dotLines = (s: string): string[] => {
  const parts: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of clean(s)) {
    if ("（(【[".includes(ch)) depth++;
    if ("）)】]".includes(ch)) depth = Math.max(0, depth - 1);
    if (ch === "·" && depth === 0) {
      parts.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  if (cur.trim()) parts.push(cur.trim());
  const lines: string[] = [];
  for (let i = 0; i < parts.length; i += 2) lines.push(parts.slice(i, i + 2).join(" · "));
  return lines.map((l) => {
    // a bracketed tail may still hold dots: keep at most one per line
    let seen = 0;
    return l.replace(/·/g, () => (seen++ === 0 ? "·" : "/"));
  });
};

/** Conservative advance width (em) per glyph: CJK 1.0, Latin caps ~0.72 (Montserrat), digits/lower ~0.62. */
export const estimateWidth = (text: string, fontSize: number, latinEm = 0.72): number =>
  [...text].reduce((w, c) => w + fontSize * (/[\u3000-\u9fff\uff00-\uffef]/.test(c) ? 1 : /[A-Z0-9]/.test(c) ? latinEm : c === " " ? 0.3 : 0.62), 0);
/** Largest font size ≤ max whose estimated width fits maxWidth (never clip; shrink instead). */
export const fitFont = (text: string, max: number, maxWidth: number, min = 18, latinEm = 0.72): number => {
  const w = estimateWidth(text, max, latinEm);
  return w <= maxWidth ? max : Math.max(min, Math.floor((max * maxWidth) / w));
};

/** Relative luminance (WCAG) of #RRGGBB. */
export const luminance = (hex: string): number => {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return 0.5;
  const n = parseInt(m[1], 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
};
/** Ink with the higher WCAG contrast on a solid fill (off-black or off-white). */
export const onColor = (fill: string): string => {
  const L = luminance(fill);
  const cBlack = (L + 0.05) / (luminance(OFF_BLACK) + 0.05);
  const cWhite = (luminance(OFF_WHITE) + 0.05) / (L + 0.05);
  return cBlack >= cWhite ? OFF_BLACK : OFF_WHITE;
};
