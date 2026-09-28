// Opener + chapter-title effects. Motion grammar after video-shotcraft cards
// blur-slide, lead-word-zoom-assemble, brand-frame-snap, marker-underline-title, brace-expand
// (Apache-2.0). Re-skinned: colours/fonts come from the active StyleTokens only.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, ease, lerp, prog, rand, subOf, titleOf } from "./kit";

const W = 1440;
const H = 1080;

const chapterText = (p: EffectProps): string =>
  p.shot.room?.zh ?? p.shot.spec?.title ?? p.shot.location?.main ?? titleOf(p.project);

/** blur-slide: words rise 40px while blur 10→0 and opacity 0→1 on one outCubic; subtitle follows. */
export const BlurSlide: React.FC<EffectProps> = ({ st, project }) => {
  const f = useCurrentFrame();
  const words = [...titleOf(project)];
  const sub = subOf(project);
  const line = (t: number, i: number, gap: number, dy: number) => {
    const k = ease.outCubic(Math.min(1, Math.max(0, (t - i * gap) / 0.32)));
    return { opacity: k, transform: `translateY(${lerp(k, dy, 0)}px)`, filter: `blur(${(1 - k) * 10}px)`, display: "inline-block" as const };
  };
  const t1 = prog(f, 2, 40);
  const t2 = prog(f, 14, 52);
  return (
    <div style={{ position: "absolute", left: 0, top: 120, width: W, textAlign: "center" }}>
      <div style={{ fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: 104, color: st.text, textShadow: st.hardShadow ?? st.textGlow, letterSpacing: 2 }}>
        {words.map((c, i) => (
          <span key={i} style={line(t1, i, 0.05, 40)}>{c}</span>
        ))}
      </div>
      {sub ? (
        <div style={{ marginTop: 18, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 38, color: st.accent, textShadow: st.textGlow }}>
          {sub.split(" · ").map((w, i) => (
            <span key={i} style={{ ...line(t2, i, 0.12, 26), margin: "0 14px" }}>{w}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

/** lead-word-zoom-assemble: first word fills the frame (2.3x), creeps 6%, then one curve shrinks it home while the rest slides in. */
export const LeadWordZoom: React.FC<EffectProps> = ({ st, project }) => {
  const f = useCurrentFrame();
  const title = titleOf(project);
  const chars = [...title];
  const lead = chars.slice(0, Math.min(2, chars.length)).join("");
  const rest = chars.slice(lead.length).join("");
  const hold = prog(f, 0, 22);
  const k = prog(f, 22, 40, ease.inOutCubic);
  const scale = lerp(k, 2.3 * (1 + 0.06 * hold), 1);
  const restK = prog(f, 30, 44, ease.outCubic);
  const subK = prog(f, 36, 50, ease.outCubic);
  const size = 110;
  return (
    <div style={{ position: "absolute", left: 0, top: 0, width: W, height: 560, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", alignItems: "baseline", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: size, color: st.text, textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>
        <span style={{ display: "inline-block", transform: `scale(${scale}) translateX(${lerp(k, rest ? size * 0.5 * [...rest].length * 0.5 : 0, 0)}px)`, transformOrigin: "center", color: k < 1 ? st.accent : st.text }}>{lead}</span>
        <span style={{ display: "inline-block", opacity: restK, transform: `translateX(${lerp(restK, 60, 0)}px)` }}>{rest}</span>
      </div>
      <div style={{ opacity: subK, transform: `translateY(${lerp(subK, 16, 0)}px)`, marginTop: 20, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 36, color: st.text, textShadow: st.textGlow }}>{subOf(project)}</div>
    </div>
  );
};

/** brand-frame-snap: a thick accent frame grows around the screen before the content, one hard colour flip, then quiet wrapper. */
export const BrandFrame: React.FC<EffectProps> = ({ st, project, duration }) => {
  const f = useCurrentFrame();
  const grow = prog(f, 0, 12, ease.outExpo);
  const flip = f >= 26 && f < 30;
  const fade = 1 - prog(f, duration - 10, duration);
  const bw = 26 * grow;
  const col = flip ? st.text : st.accent;
  const tK = prog(f, 12, 22, ease.outCubic);
  return (
    <>
      <div style={{ position: "absolute", inset: 0, boxShadow: `inset 0 0 0 ${bw}px ${col}`, opacity: fade }} />
      <div style={{ position: "absolute", left: 60, top: 70, opacity: tK * fade, transform: `translateX(${lerp(tK, -30, 0)}px)` }}>
        <div style={{ display: "inline-block", background: col, color: st.dark, fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: 64, padding: "8px 26px" }}>{titleOf(project)}</div>
        <div style={{ marginTop: 10, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 32, color: st.text, textShadow: st.textGlow }}>{subOf(project)}</div>
      </div>
    </>
  );
};

/** marker-underline-title: title settles (22f), a beat later a variable-width marker stroke wipes under it (10f). */
export const MarkerUnderline: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const f = useCurrentFrame();
  const text = chapterText(p);
  const enter = prog(f, 0, 22, ease.outCubic);
  const draw = prog(f, 26, 36, (t) => 1 - Math.pow(1 - t, 2.2));
  const len = Math.min(1100, [...text].length * 130 + 40);
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
    <div style={{ position: "absolute", left: 0, top: 300, width: W, display: "flex", justifyContent: "center" }}>
      <div style={{ position: "relative", opacity: Math.min(1, enter * 1.6), transform: `translateY(${(1 - enter) * 36}px)` }}>
        <svg width={len} height={50} style={{ position: "absolute", left: -20, bottom: -18, overflow: "visible" }}>
          <path d={d} fill={alpha(st.accent, 0.92)} style={{ clipPath: `inset(0 ${(1 - draw) * 100}% 0 0)` }} />
        </svg>
        <div style={{ position: "relative", fontFamily: st.fonts.roomZh, fontWeight: st.fonts.roomZhWeight, fontSize: 128, color: st.text, textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>{text}</div>
      </div>
    </div>
  );
};

/** brace-expand: a pair of braces appears small, overshoots outward to title size, text clip width bound to brace gap. */
export const BraceExpand: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const f = useCurrentFrame();
  const text = chapterText(p);
  const target = Math.min(620, [...text].length * 70 + 60);
  const k = prog(f, 7, 25, (t) => ease.outBack(t, 1.9));
  const gap = lerp(Math.max(0, k), 30, target);
  const size = lerp(prog(f, 7, 22, ease.outCubic), 70, 150);
  const appear = prog(f, 0, 7);
  const spacing = lerp(prog(f, 25, 55, ease.outCubic), 0, 6);
  return (
    <div style={{ position: "absolute", left: 0, top: H / 2 - 170, width: W, height: 220, opacity: appear }}>
      <div style={{ position: "absolute", left: W / 2 - gap - size * 0.4, top: 0, fontFamily: st.fonts.latin, fontWeight: 300, fontSize: size * 1.3, color: st.accent, lineHeight: 1 }}>{"{"}</div>
      <div style={{ position: "absolute", left: W / 2 + gap - size * 0.25, top: 0, fontFamily: st.fonts.latin, fontWeight: 300, fontSize: size * 1.3, color: st.accent, lineHeight: 1 }}>{"}"}</div>
      <div style={{ position: "absolute", left: W / 2 - gap + 20, width: Math.max(0, gap * 2 - 40), top: size * 0.12, overflow: "hidden", textAlign: "center", whiteSpace: "nowrap", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: 118, letterSpacing: spacing, color: st.text, textShadow: st.hardShadow ?? st.textGlow }}>{text}</div>
    </div>
  );
};
