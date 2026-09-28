// Opener + chapter-title effects. Motion grammar after video-shotcraft cards
// blur-slide, lead-word-zoom-assemble, brand-frame-snap, marker-underline-title, brace-expand
// (Apache-2.0). Re-skinned: colours/fonts come from the active StyleTokens only.
// Layout follows video-taste: title-safe top band (openers sit above the presenter's face),
// never inside the caption band, ≤5 simultaneous animators, off-white ink, one label family.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, chip, clean, ease, fitFont, ink, lerp, prog, rand, scrim, slab, subParts, titleOf } from "./kit";

const W = 1440;
const SIDE = 96; // title-safe sides
const TOP = 88; // title-safe top (≥72)

const chapterText = (p: EffectProps): string => clean(p.shot.room?.zh ?? p.shot.spec?.title ?? p.shot.location?.main ?? titleOf(p.project));

/** Staggered units: 10 f each, 4 f apart → never more than 3 moving at once. */
const unit = (f: number, start: number, i: number) => ease.outCubic(Math.min(1, Math.max(0, (f - start - i * 4) / 10)));

/** Sub facts as spaced parts in one row (no middle-dot chains). */
const SubRow: React.FC<{ parts: string[]; st: EffectProps["st"]; k: number; size?: number; color?: string }> = ({ parts, st, k, size = 34, color }) => (
  <div style={{ display: "flex", justifyContent: "center", gap: 28, opacity: k, transform: `translateY(${lerp(k, 14, 0)}px)`, fontFamily: st.fonts.sans, fontWeight: 700, fontSize: size, color: color ?? ink(st), textShadow: st.textGlow, whiteSpace: "nowrap" }}>
    {parts.map((x) => (
      <span key={x}>{x}</span>
    ))}
  </div>
);

/** blur-slide: characters rise 40px while blur 10→0 and opacity 0→1 (outCubic); subtitle follows as one unit. */
export const BlurSlide: React.FC<EffectProps> = ({ st, project }) => {
  const f = useCurrentFrame();
  const title = titleOf(project);
  const chars = [...title];
  const size = fitFont(title, 104, W - 2 * SIDE);
  const subK = unit(f, 2 + chars.length * 4 + 6, 0);
  return (
    <div style={{ position: "absolute", left: SIDE, width: W - 2 * SIDE, top: TOP, textAlign: "center" }}>
      <div style={{ position: "absolute", left: "10%", width: "80%", top: -40, height: size + 140, ...scrim(st, 0.5) }} />
      <div style={{ position: "relative", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: size, lineHeight: 1.1, color: ink(st), textShadow: st.hardShadow ?? st.textGlow }}>
        {chars.map((c, i) => {
          const k = unit(f, 2, i);
          return (
            <span key={i} style={{ display: "inline-block", opacity: k, transform: `translateY(${lerp(k, 40, 0)}px)`, filter: `blur(${(1 - k) * 10}px)` }}>{c}</span>
          );
        })}
      </div>
      <div style={{ position: "relative", marginTop: 14 }}>
        <SubRow parts={subParts(project)} st={st} k={subK} color={st.accent} />
      </div>
    </div>
  );
};

/** lead-word-zoom-assemble: first word fills the top band (1.8x), creeps 6%, then one curve shrinks it home while the rest slides in. */
export const LeadWordZoom: React.FC<EffectProps> = ({ st, project }) => {
  const f = useCurrentFrame();
  const title = titleOf(project);
  const chars = [...title];
  const lead = chars.slice(0, Math.min(2, chars.length)).join("");
  const rest = chars.slice(lead.length).join("");
  const size = fitFont(title, 110, W - 2 * SIDE);
  const hold = prog(f, 0, 22);
  const k = prog(f, 22, 38, ease.inOutCubic);
  const scale = lerp(k, 1.8 * (1 + 0.06 * hold), 1);
  const restK = prog(f, 30, 42, ease.outCubic);
  const subK = prog(f, 38, 50, ease.outCubic);
  const shift = rest ? (size * [...rest].length) / 2 : 0;
  return (
    <div style={{ position: "absolute", left: SIDE, width: W - 2 * SIDE, top: TOP, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ position: "absolute", left: "8%", width: "84%", top: -30, height: size + 150, ...scrim(st, 0.5) }} />
      <div style={{ position: "relative", display: "flex", alignItems: "baseline", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: size, lineHeight: 1.1, color: ink(st), textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>
        <span style={{ display: "inline-block", transform: `translateX(${lerp(k, shift, 0)}px) scale(${scale})`, transformOrigin: "center top", color: k < 1 ? st.accent : ink(st) }}>{lead}</span>
        <span style={{ display: "inline-block", opacity: restK, transform: `translateX(${lerp(restK, 60, 0)}px)` }}>{rest}</span>
      </div>
      <div style={{ position: "relative", marginTop: 14 }}>
        <SubRow parts={subParts(project)} st={st} k={subK} />
      </div>
    </div>
  );
};

/** brand-frame-snap: a thick accent frame grows around the screen before the content, one hard colour flip, then quiet wrapper. */
export const BrandFrame: React.FC<EffectProps> = ({ st, project, duration }) => {
  const f = useCurrentFrame();
  const grow = prog(f, 0, 12, ease.outExpo);
  const flip = f >= 26 && f < 30;
  const fade = 1 - prog(f, duration - 10, duration);
  const col = flip ? ink(st) : st.accent;
  const tK = prog(f, 12, 22, ease.outCubic);
  const subK = prog(f, 18, 28, ease.outCubic);
  const title = titleOf(project);
  return (
    <>
      <div style={{ position: "absolute", inset: 0, boxShadow: `inset 0 0 0 ${24 * grow}px ${col}`, opacity: fade }} />
      <div style={{ position: "absolute", left: SIDE, top: TOP, opacity: fade }}>
        <div style={{ ...slab(st), background: col, display: "inline-block", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: fitFont(title, 64, 700), opacity: tK, transform: `translateX(${lerp(tK, -30, 0)}px)` }}>{title}</div>
        <div style={{ marginTop: 12, display: "flex", gap: 12, opacity: subK, transform: `translateY(${lerp(subK, 12, 0)}px)` }}>
          {subParts(project).map((x) => (
            <span key={x} style={{ ...chip(st), fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 30, color: ink(st) }}>{x}</span>
          ))}
        </div>
      </div>
    </>
  );
};

/** marker-underline-title: title settles (22f), a beat later a variable-width marker stroke wipes under it (10f). */
export const MarkerUnderline: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const f = useCurrentFrame();
  const text = chapterText(p);
  const size = fitFont(text, 128, W - 2 * SIDE - 40);
  const enter = prog(f, 0, 22, ease.outCubic);
  const draw = prog(f, 26, 36, (t) => 1 - Math.pow(1 - t, 2.2));
  const len = Math.min(W - 2 * SIDE, [...text].length * size + 40);
  const r = rand(77);
  const N = 36;
  const top: string[] = [];
  const bot: string[] = [];
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    const wob = r() - 0.5;
    const mid = 22 - t * 8 + Math.sin(t * Math.PI * 1.6 + 0.4) * 3 + wob * 2;
    const w = Math.max(3, 22 + Math.sin(t * Math.PI) * 8 - Math.max(0, t - 0.86) * 70 + wob * 4);
    top.push(`${(t * len).toFixed(1)},${(mid - w / 2).toFixed(1)}`);
    bot.push(`${(t * len).toFixed(1)},${(mid + w / 2).toFixed(1)}`);
  }
  const d = `M${top.join("L")}L${bot.reverse().join("L")}Z`;
  return (
    <div style={{ position: "absolute", left: SIDE, width: W - 2 * SIDE, top: 300, display: "flex", justifyContent: "center" }}>
      <div style={{ position: "relative", opacity: Math.min(1, enter * 1.6), transform: `translateY(${(1 - enter) * 36}px)` }}>
        <div style={{ position: "absolute", left: -80, right: -80, top: -60, bottom: -60, ...scrim(st, 0.5) }} />
        <svg width={len} height={50} style={{ position: "absolute", left: -20, bottom: -18, overflow: "visible" }}>
          <path d={d} fill={alpha(st.accent, 0.92)} style={{ clipPath: `inset(0 ${(1 - draw) * 100}% 0 0)` }} />
        </svg>
        <div style={{ position: "relative", fontFamily: st.fonts.roomZh, fontWeight: st.fonts.roomZhWeight, fontSize: size, lineHeight: 1.1, color: ink(st), textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>{text}</div>
      </div>
    </div>
  );
};

/** brace-expand: a pair of braces appears small, overshoots outward to title size, text clip width bound to brace gap. */
export const BraceExpand: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const f = useCurrentFrame();
  const text = chapterText(p);
  const textSize = fitFont(text, 118, W - 2 * SIDE - 260);
  const target = Math.min((W - 2 * SIDE - 220) / 2, ([...text].length * textSize) / 2 + 40);
  const k = prog(f, 7, 21, (t) => ease.outBack(t, 1.2)); // overshoot ≈10 %
  const gap = lerp(Math.max(0, k), 30, target);
  const size = lerp(prog(f, 7, 21, ease.outCubic), 70, 150);
  const appear = prog(f, 0, 7);
  const spacing = lerp(prog(f, 21, 50, ease.outCubic), 0, 6);
  const top = 370;
  return (
    <div style={{ position: "absolute", left: 0, top, width: W, height: 220, opacity: appear }}>
      <div style={{ position: "absolute", left: W / 2 - target - 120, width: target * 2 + 240, top: -40, height: 300, ...scrim(st, 0.45) }} />
      <div style={{ position: "absolute", left: W / 2 - gap - size * 0.55, top: 0, fontFamily: st.fonts.latin, fontWeight: 300, fontSize: size * 1.3, color: st.accent, lineHeight: 1 }}>{"{"}</div>
      <div style={{ position: "absolute", left: W / 2 + gap - size * 0.1, top: 0, fontFamily: st.fonts.latin, fontWeight: 300, fontSize: size * 1.3, color: st.accent, lineHeight: 1 }}>{"}"}</div>
      <div style={{ position: "absolute", left: W / 2 - gap + 10, width: Math.max(0, gap * 2 - 20), top: size * 0.14, overflow: "hidden", textAlign: "center", whiteSpace: "nowrap", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: textSize, lineHeight: 1.1, letterSpacing: spacing, color: ink(st), textShadow: st.hardShadow ?? st.textGlow }}>{text}</div>
    </div>
  );
};

