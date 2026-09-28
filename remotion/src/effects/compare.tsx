// Comparison effects (listing wall / A-vs-B). Motion grammar after video-shotcraft cards
// before-after-slider-scrub and value-stagger-gradient (Apache-2.0). Re-skinned to StyleTokens.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, ease, lerp, prog, priceOf } from "./kit";

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
  // whip 0→0.85 in 8f, then slow scan back to 0.35 (reading beat)
  const x = lf < 8 ? lerp(ease.outCubic(lf / 8), 0.02, 0.85) : lerp(prog(lf, 8, Math.max(20, duration - start - 6), ease.inOutCubic), 0.85, 0.35);
  const cut = x * W;
  const others = Math.max(0, (wall?.cards.length ?? 1) - 1);
  return (
    <AbsoluteFill style={{ opacity: inK }}>
      <Img src={srcOf(img)} style={{ position: "absolute", inset: 0, width: W, height: H, objectFit: "cover", filter: "grayscale(1) brightness(.6)" }} />
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 0 0 ${cut}px)` }}>
        <Img src={srcOf(img)} style={{ width: W, height: H, objectFit: "cover", filter: st.grade }} />
      </div>
      <div style={{ position: "absolute", left: cut - 3, top: 0, width: 6, height: H, background: st.accent, boxShadow: `0 0 18px ${alpha(st.accent, 0.7)}` }} />
      <div style={{ position: "absolute", left: cut - 30, top: H / 2 - 30, width: 60, height: 60, borderRadius: 30, background: st.accent, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 28, color: st.dark }}>{"<>"}</div>
      <div style={{ position: "absolute", left: 60, top: 120, fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 36, color: "#fff", background: "rgba(0,0,0,.45)", padding: "6px 16px", borderRadius: 6 }}>{others ? `其余 ${others} 套候选` : "候选"}</div>
      <div style={{ position: "absolute", right: 60, top: 120, fontFamily: st.fonts.sans, fontWeight: 800, fontSize: 36, color: st.dark, background: st.accent, padding: "6px 16px", borderRadius: 6 }}>本期房源</div>
    </AbsoluteFill>
  );
};

/** value-stagger-gradient → two fact columns rise with staggered delay and a value gradient (area | rent). Facts only. */
export const DualStat: React.FC<EffectProps> = ({ st, project, duration }) => {
  const f = useCurrentFrame();
  const start = Math.round(duration * 0.55);
  const lf = f - start;
  if (lf < 0) return null;
  const pr = priceOf(project);
  const stats = [
    { k: "面积", v: `${project.property.area.value}`, u: "㎡" },
    { k: project.price.type || "价格", v: pr.value, u: pr.unit },
  ];
  return (
    <div style={{ position: "absolute", left: 0, top: 780, width: W, display: "flex", justifyContent: "center", gap: 40 }}>
      {stats.map((s, i) => {
        const k = prog(lf, i * 5, i * 5 + 12, ease.outCubic);
        return (
          <div key={s.k} style={{ width: 460, padding: "18px 26px", borderRadius: 14, background: alpha(st.dark, 0.78), borderTop: `6px solid ${st.accent}`, opacity: k, transform: `translateY(${lerp(k, 40, 0)}px)`, filter: `blur(${(1 - k) * 6}px)` }}>
            <div style={{ fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 28, color: alpha("#FFFFFF", 0.75) }}>{s.k}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 84, color: i === 0 ? st.text : st.gold }}>{s.v}</span>
              <span style={{ fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 30, color: st.text }}>{s.u}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
