// Comparison effects (listing wall / A-vs-B). Motion grammar after video-shotcraft cards
// before-after-slider-scrub and value-stagger-gradient (Apache-2.0). Re-skinned to StyleTokens.
// video-taste: labels use the shared chip family (+ one accent slab), stats yield to caption band + PiP.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, bottomLimit, card, chip, ease, ink, lerp, prog, priceOf, SAFE, shade, slab } from "./kit";

const W = 1440;
const H = 1080;
const srcOf = (p: string) => (/^(https?:|data:)/.test(p) ? p : staticFile(p));

/** before-after-slider-scrub: two versions stacked; divider whips across fast, then scans slowly. Here: other candidates (grey) → picked listing. */
export const BeforeAfterSlider: React.FC<EffectProps> = ({ st, project, duration }) => {
  const f = useCurrentFrame();
  const wall = project.wall;
  const picked = wall?.cards.find((c) => c.id === wall.picked) ?? wall?.cards[0];
  const img = picked?.cover ?? project.shots?.shots.find((s) => s.media)?.media;
  const start = Math.round(duration * 0.55);
  const lf = f - start;
  if (lf < 0 || !img) return null;
  const inK = prog(lf, 0, 6);
  // whip 0→0.85 in 8f, then slow scan back to 0.35 (reading beat) — keeps moving until the cut
  const x = lf < 8 ? lerp(ease.outCubic(lf / 8), 0.02, 0.85) : lerp(prog(lf, 8, Math.max(20, duration - start), ease.inOutCubic), 0.85, 0.35);
  const cut = x * W;
  const others = Math.max(0, (wall?.cards.length ?? 1) - 1);
  const labelTop = 96;
  return (
    <AbsoluteFill style={{ opacity: inK }}>
      <Img src={srcOf(img)} style={{ position: "absolute", inset: 0, width: W, height: H, objectFit: "cover", filter: "grayscale(1) brightness(.6)" }} />
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 0 0 ${cut}px)` }}>
        <Img src={srcOf(img)} style={{ width: W, height: H, objectFit: "cover", filter: st.grade }} />
      </div>
      <div style={{ position: "absolute", left: cut - 3, top: 0, width: 6, height: H, background: st.accent, boxShadow: shade(st, 0.4, 14, 0) }} />
      <div style={{ position: "absolute", left: cut - 28, top: 420, width: 56, height: 56, borderRadius: 28, background: st.accent, boxShadow: shade(st, 0.3, 10, 3) }}>
        <svg width={40} height={40} style={{ margin: 8 }} viewBox="0 0 24 24" fill="none" stroke={alpha(st.dark, 1)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          {/* Tabler Icons "arrows-horizontal" (MIT, tabler.io/icons), stroke 2 */}
          <path d="M7 8l-4 4l4 4" />
          <path d="M17 8l4 4l-4 4" />
          <path d="M3 12l18 0" />
        </svg>
      </div>
      <div style={{ position: "absolute", left: SAFE + 48, top: labelTop, ...chip(st), fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 34, color: ink(st) }}>{others ? `其余 ${others} 套候选` : "候选"}</div>
      <div style={{ position: "absolute", right: SAFE + 48, top: labelTop, ...slab(st), fontFamily: st.fonts.sans, fontWeight: 800, fontSize: 34 }}>本期房源</div>
    </AbsoluteFill>
  );
};

/** value-stagger-gradient → two fact cards rise with staggered delay (area | rent). Facts only; placed above the caption band, clear of the PiP. */
export const DualStat: React.FC<EffectProps> = ({ st, project, duration, zones }) => {
  const f = useCurrentFrame();
  const start = Math.round(duration * 0.55);
  const lf = f - start;
  if (lf < 0) return null;
  const pr = priceOf(project);
  const stats = [
    { k: "面积", v: `${project.property.area.value}`, u: "㎡" },
    { k: project.price.type || "价格", v: pr.value, u: pr.unit },
  ];
  const cw = 400;
  const gap = 28;
  const x0 = 96;
  const x1 = x0 + cw * 2 + gap;
  const ch = 150;
  const top = bottomLimit(zones, x0, x1) - ch;
  const settle = lerp(prog(lf, 17, Math.max(18, duration - start), ease.linear), 0, -8);
  return (
    <div style={{ position: "absolute", left: x0, top, display: "flex", gap, transform: `translateY(${settle}px)` }}>
      {stats.map((s, i) => {
        const k = prog(lf, i * 5, i * 5 + 12, ease.outCubic);
        return (
          <div key={s.k} style={{ ...card(st), width: cw, height: ch, boxSizing: "border-box", padding: "16px 24px", borderTop: `6px solid ${st.accent}`, opacity: k, transform: `translateY(${lerp(k, 40, 0)}px)`, filter: `blur(${(1 - k) * 6}px)` }}>
            <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 28, color: alpha("#FBFBF8", 0.8) }}>{s.k}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 76, lineHeight: 1.1, fontVariantNumeric: "tabular-nums", color: i === 0 ? ink(st) : st.gold }}>{s.v}</span>
              <span style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 30, color: ink(st) }}>{s.u}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
