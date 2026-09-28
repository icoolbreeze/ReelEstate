// List / checklist + CTA effects. Motion grammar after video-shotcraft cards list-reveal,
// list-stack-press, logo-shrink-wordmark-lockup and grain-dissolve (settle only — no grain burst)
// (Apache-2.0). Re-skinned to StyleTokens.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, ease, lerp, prog, titleOf } from "./kit";

const W = 1440;

const listOf = (p: EffectProps) => ({
  title: p.shot.spec?.title ?? "HEADS-UP",
  lines: (p.shot.spec?.lines?.length ? p.shot.spec.lines : p.project.drawbacks).slice(0, 5),
  warn: p.shot.spec?.variant === "warning",
});

/** list-reveal: items scale into place one by one (outBack, slight overshoot) while the whole list drifts up linearly. */
export const ListReveal: React.FC<EffectProps> = (p) => {
  const { st, duration } = p;
  const f = useCurrentFrame();
  const { title, lines, warn } = listOf(p);
  const drift = lerp(prog(f, 0, duration), 20, -20);
  const head = prog(f, 0, 8, ease.outCubic);
  return (
    <div style={{ position: "absolute", left: 90, top: 190, width: 820, transform: `translateY(${drift}px)` }}>
      <div style={{ opacity: head, fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 56, color: warn ? st.red : st.accent, letterSpacing: 2, marginBottom: 18, textShadow: st.textGlow }}>{title}</div>
      {lines.map((l, i) => {
        const k = prog(f, 6 + i * 5, 6 + i * 5 + 10, ease.outBack);
        const kk = Math.max(0, k);
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 14, padding: "14px 22px", borderRadius: 12, background: alpha(st.dark, 0.72), borderLeft: `6px solid ${warn ? st.red : st.accent}`, opacity: Math.min(1, kk * 2.2), transform: `scale(${0.78 + kk * 0.22}) translateY(${lerp(kk, 14, 0)}px)`, transformOrigin: "left center" }}>
            <div style={{ width: 16, height: 16, borderRadius: 8, background: warn ? st.red : st.accent, flex: "none" }} />
            <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 40, color: st.text }}>{l}</div>
          </div>
        );
      })}
    </div>
  );
};

/** list-stack-press: cards fly up from the bottom and stack; each landing presses the stack and ticks a counter. */
export const ChecklistStack: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const f = useCurrentFrame();
  const { title, lines, warn } = listOf(p);
  const step = 9;
  const landed = lines.filter((_, i) => f >= 4 + i * step + 8).length;
  const lastLand = 4 + Math.max(0, landed - 1) * step + 8;
  const press = landed ? prog(f, lastLand, lastLand + 3) * (1 - prog(f, lastLand + 3, lastLand + 8)) : 0;
  const col = warn ? st.red : st.accent;
  return (
    <div style={{ position: "absolute", left: 90, top: 170, width: 860 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 20 }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 56, color: col, letterSpacing: 2, textShadow: st.textGlow }}>{title}</div>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 40, color: st.dark, background: col, borderRadius: 30, padding: "2px 18px", fontVariantNumeric: "tabular-nums" }}>{landed}/{lines.length}</div>
      </div>
      <div style={{ transform: `scaleY(${1 - 0.03 * press})`, transformOrigin: "top" }}>
        {lines.map((l, i) => {
          const k = prog(f, 4 + i * step, 4 + i * step + 8, ease.outCubic);
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 12, padding: "16px 24px", borderRadius: 12, background: "rgba(255,255,255,.94)", boxShadow: "0 8px 20px rgba(0,0,0,.25)", opacity: k > 0 ? 1 : 0, transform: `translateY(${lerp(k, 700, 0)}px)` }}>
              <div style={{ width: 34, height: 34, borderRadius: 8, border: `4px solid ${col}`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: st.fonts.latin, fontWeight: 900, fontSize: 24, color: col, flex: "none" }}>{f >= 4 + i * step + 8 ? "!" : ""}</div>
              <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 38, color: "#161616" }}>{l}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/** logo-shrink-wordmark-lockup: a big accent ring snaps down to a solid dot (overshoot brake), shifts left, wordmark letters slide in, CTA tag lands. */
export const CtaLockup: React.FC<EffectProps> = ({ st, shot, project }) => {
  const f = useCurrentFrame();
  const cta = shot.cta ?? "点击下方组件 预约看房";
  const shrink = prog(f, 0, 12, (t) => ease.outBack(t, 1.4));
  const r = lerp(Math.min(1.08, shrink), 420, 44);
  const shift = prog(f, 16, 26, ease.inOutCubic);
  const word = [...titleOf(project)];
  const cx = W / 2 - shift * (word.length * 36 + 40);
  const cy = 500;
  const ctaK = prog(f, 34 + word.length * 2, 44 + word.length * 2, ease.outCubic);
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", left: cx - r, top: cy - r, width: r * 2, height: r * 2, borderRadius: "50%", boxSizing: "border-box", border: shrink < 0.9 ? `${lerp(shrink, 10, 44)}px solid ${st.accent}` : undefined, background: shrink >= 0.9 ? st.accent : undefined }} />
      <div style={{ position: "absolute", left: cx + 70, top: cy - 48, display: "flex" }}>
        {word.map((c, i) => {
          const k = prog(f, 24 + i * 2, 32 + i * 2, ease.outCubic);
          return <span key={i} style={{ display: "inline-block", opacity: k, transform: `translateX(${lerp(k, -30, 0)}px)`, fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: 80, color: st.text, lineHeight: "96px", textShadow: st.textGlow }}>{c}</span>;
        })}
      </div>
      <div style={{ position: "absolute", left: 0, width: W, top: 640, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, opacity: ctaK, transform: `translateY(${lerp(ctaK, 20, 0)}px)` }}>
        <div style={{ background: st.accent, color: "#111", fontFamily: st.fonts.sans, fontWeight: 900, fontSize: 54, padding: "12px 38px", borderRadius: 60 }}>{cta}</div>
        <div style={{ fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 28, color: st.text, textShadow: "0 2px 8px rgba(0,0,0,.6)" }}>{project.agency.full_name}</div>
      </div>
    </div>
  );
};

/** Wordmark settle: large blurred wordmark condenses (blur 18→0, letter-spacing 40→4) and comes to rest; CTA follows. No shake/particles. */
export const WordmarkSettle: React.FC<EffectProps> = ({ st, shot, project }) => {
  const f = useCurrentFrame();
  const cta = shot.cta ?? "点击下方组件 预约看房";
  const k = prog(f, 0, 22, ease.outCubic);
  const ctaK = prog(f, 22, 32, ease.outCubic);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: 380, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: lerp(k, 150, 110), letterSpacing: lerp(k, 40, 4), color: st.text, filter: `blur(${(1 - k) * 18}px)`, opacity: Math.min(1, k * 1.5), textShadow: `0 0 30px ${alpha(st.accent, 0.35 * k)}` }}>{titleOf(project)}</div>
      <div style={{ width: lerp(ctaK, 0, 360), height: 5, background: st.accent, margin: "18px 0 26px", borderRadius: 3 }} />
      <div style={{ opacity: ctaK, transform: `scale(${0.92 + 0.08 * ctaK})`, background: st.accent, color: "#111", fontFamily: st.fonts.sans, fontWeight: 900, fontSize: 54, padding: "12px 38px", borderRadius: 60 }}>{cta}</div>
      <div style={{ opacity: ctaK, marginTop: 14, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 28, color: st.text, textShadow: "0 2px 8px rgba(0,0,0,.6)" }}>{project.agency.full_name}</div>
    </div>
  );
};
