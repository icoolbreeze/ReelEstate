// List / checklist + CTA effects. Motion grammar after video-shotcraft cards list-reveal,
// list-stack-press, logo-shrink-wordmark-lockup and grain-dissolve (settle only; no grain burst)
// (Apache-2.0). Re-skinned to StyleTokens. video-taste: rows are the shared dark card family
// (no light cards next to dark chips, no decorative dots), the list fits between its title and the
// caption band / PiP, the CTA block stays above the caption band, ≤5 animators at once.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, bottomLimit, card, clean, dotLines, ease, fitFont, ink, lerp, onColor, prog, scrim, slab, titleOf } from "./kit";

const W = 1440;
const LEFT = 96;
const LIST_W = 860;
const TOP = 160;

const listOf = (p: EffectProps) => ({
  title: clean(p.shot.spec?.title ?? "HEADS-UP"),
  lines: (p.shot.spec?.lines?.length ? p.shot.spec.lines : p.project.drawbacks).slice(0, 5).map((l) => dotLines(l).join(" ")),
  warn: p.shot.spec?.variant === "warning",
});

/** Fit n rows between the title and the caption band / PiP: returns row height + font size. */
const fitRows = (p: EffectProps, n: number, headH: number) => {
  const limit = bottomLimit(p.zones, LEFT, LEFT + LIST_W);
  const avail = limit - TOP - headH;
  const rowH = Math.min(84, Math.floor(avail / Math.max(1, n)));
  return { rowH, font: Math.max(26, Math.min(40, Math.floor((rowH - 12) * 0.62))), gap: Math.max(8, Math.min(14, rowH - 64)) };
};

/** list-reveal: items scale into place one by one (outBack, slight overshoot) while the whole list drifts up linearly. */
export const ListReveal: React.FC<EffectProps> = (p) => {
  const { st, duration } = p;
  const f = useCurrentFrame();
  const { title, lines, warn } = listOf(p);
  const col = warn ? st.red : st.accent;
  const headH = 80;
  const { rowH, font, gap } = fitRows(p, lines.length, headH);
  const drift = lerp(prog(f, 0, duration), 12, -12);
  const head = prog(f, 0, 8, ease.outCubic);
  return (
    <div style={{ position: "absolute", left: LEFT, top: TOP, width: LIST_W, transform: `translateY(${drift}px)` }}>
      <div style={{ position: "absolute", left: -60, width: 620, top: -30, height: headH + 30, ...scrim(st, 0.5), opacity: head }} />
      <div style={{ position: "relative", height: headH, opacity: head, fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 56, lineHeight: 1.1, color: col, letterSpacing: 2, textShadow: st.textGlow }}>{title}</div>
      {lines.map((l, i) => {
        const k = prog(f, 6 + i * 5, 6 + i * 5 + 10, (t) => ease.outBack(t, 1.2));
        const kk = Math.max(0, k);
        return (
          <div key={i} style={{ ...card(st), display: "flex", alignItems: "center", height: rowH - gap, marginBottom: gap, padding: "0 24px", boxSizing: "border-box", borderLeft: `6px solid ${col}`, opacity: Math.min(1, kk * 2.2), transform: `scale(${0.8 + kk * 0.2}) translateY(${lerp(kk, 14, 0)}px)`, transformOrigin: "left center" }}>
            <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: fitFont(l, font, LIST_W - 60, 22), color: ink(st), whiteSpace: "nowrap" }}>{l}</div>
          </div>
        );
      })}
    </div>
  );
};

/** list-stack-press: cards fly up from below and stack; each landing presses the stack and ticks a counter. */
export const ChecklistStack: React.FC<EffectProps> = (p) => {
  const { st, duration } = p;
  const f = useCurrentFrame();
  const { title, lines, warn } = listOf(p);
  const col = warn ? st.red : st.accent;
  const headH = 84;
  const { rowH, font, gap } = fitRows(p, lines.length, headH);
  const step = 9;
  const landed = lines.filter((_, i) => f >= 4 + i * step + 8).length;
  const lastLand = 4 + Math.max(0, landed - 1) * step + 8;
  const press = landed ? prog(f, lastLand, lastLand + 3) * (1 - prog(f, lastLand + 3, lastLand + 8)) : 0;
  const allIn = 4 + Math.max(0, lines.length - 1) * step + 16;
  const hold = lerp(prog(f, allIn, duration, ease.linear), 0, -10); // slow settle through the reading hold
  return (
    <div style={{ position: "absolute", left: LEFT, top: TOP, width: LIST_W, transform: `translateY(${hold}px)` }}>
      <div style={{ position: "absolute", left: -60, width: 620, top: -30, height: headH + 30, ...scrim(st, 0.5) }} />
      <div style={{ position: "relative", height: headH, display: "flex", alignItems: "flex-start", gap: 18 }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 56, lineHeight: 1.1, color: col, letterSpacing: 2, textShadow: st.textGlow }}>{title}</div>
        <div style={{ ...slab(st), background: col, color: onColor(col), fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 36, fontVariantNumeric: "tabular-nums", marginTop: 6 }}>{landed}/{lines.length}</div>
      </div>
      <div style={{ transform: `scaleY(${1 - 0.03 * press})`, transformOrigin: "top" }}>
        {lines.map((l, i) => {
          const k = prog(f, 4 + i * step, 4 + i * step + 8, ease.outCubic);
          return (
            <div key={i} style={{ ...card(st), display: "flex", alignItems: "center", gap: 18, height: rowH - gap, marginBottom: gap, padding: "0 24px", boxSizing: "border-box", opacity: k > 0 ? 1 : 0, transform: `translateY(${lerp(k, 700, 0)}px)` }}>
              <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: Math.round(font * 0.8), color: col, fontVariantNumeric: "tabular-nums", flex: "none" }}>{String(i + 1).padStart(2, "0")}</div>
              <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: fitFont(l, font, LIST_W - 130, 22), color: ink(st), whiteSpace: "nowrap" }}>{l}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/** CTA pill + agency line, shared by both endings; bottom stays above the caption band. */
const CtaBlock: React.FC<EffectProps & { k: number; top: number }> = ({ st, shot, project, k, top }) => {
  const cta = clean(shot.cta ?? "点击下方组件 预约看房");
  const agency = clean(project.agency.full_name);
  return (
    <div style={{ position: "absolute", left: 96, width: W - 192, top, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, opacity: k, transform: `translateY(${lerp(k, 20, 0)}px)` }}>
      <div style={{ ...slab(st), borderRadius: 60, padding: "12px 38px", fontFamily: st.fonts.sans, fontWeight: 900, fontSize: fitFont(cta, 54, W - 300) }}>{cta}</div>
      <div style={{ position: "relative", fontFamily: st.fonts.sans, fontWeight: 700, fontSize: fitFont(agency, 30, W - 300, 22), color: ink(st), textShadow: st.textGlow }}>
        <div style={{ position: "absolute", left: -60, right: -60, top: -16, bottom: -16, ...scrim(st, 0.5) }} />
        <span style={{ position: "relative" }}>{agency}</span>
      </div>
    </div>
  );
};

const CTA_TOP = 600; // pill ≈ 90 px + agency ≈ 44 px → ends ≈ 750 (< caption band 780)

/** logo-shrink-wordmark-lockup: a big accent ring snaps down to a solid dot (≤12 % overshoot), shifts left, wordmark letters slide in, CTA lands. Lockup sits in the top band, clear of the presenter's face. */
export const CtaLockup: React.FC<EffectProps> = (p) => {
  const { st, project, duration } = p;
  const f = useCurrentFrame();
  const word = [...titleOf(project)];
  const wordSize = fitFont(word.join(""), 80, W - 2 * 96 - 200);
  const shrink = prog(f, 0, 12, (t) => ease.outBack(t, 1.2));
  const r = lerp(Math.min(1.08, shrink), 300, 40);
  const shift = prog(f, 14, 24, ease.inOutCubic);
  const lockW = 100 + word.length * wordSize;
  const cx = W / 2 - shift * (lockW / 2 - 40);
  const cy = 200;
  const charsDone = 24 + word.length * 3 + 8;
  const ctaK = prog(f, charsDone, charsDone + 10, ease.outCubic);
  const settle = 1 + 0.02 * prog(f, charsDone + 10, duration, ease.linear);
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${settle})`, transformOrigin: `${W / 2}px ${cy}px` }}>
        <div style={{ position: "absolute", left: W / 2 - lockW / 2 - 80, width: lockW + 160, top: cy - 110, height: 220, ...scrim(st, 0.5), opacity: shift }} />
        <div style={{ position: "absolute", left: cx - r, top: cy - r, width: r * 2, height: r * 2, borderRadius: "50%", boxSizing: "border-box", border: shrink < 0.9 ? `${lerp(shrink, 10, 40)}px solid ${st.accent}` : undefined, background: shrink >= 0.9 ? st.accent : undefined }} />
        <div style={{ position: "absolute", left: cx + 64, top: cy - wordSize * 0.6, display: "flex" }}>
          {word.map((c, i) => {
            const k = prog(f, 24 + i * 3, 32 + i * 3, ease.outCubic); // 3 f apart → ≤3 letters moving
            return <span key={i} style={{ display: "inline-block", opacity: k, transform: `translateX(${lerp(k, -30, 0)}px)`, fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: wordSize, color: ink(st), lineHeight: 1.15, textShadow: st.textGlow }}>{c}</span>;
          })}
        </div>
      </div>
      <CtaBlock {...p} k={ctaK} top={CTA_TOP} />
    </div>
  );
};

/** Wordmark settle: large blurred wordmark condenses (blur 18→0, letter-spacing 40→4) and comes to rest; CTA follows. No shake/particles. */
export const WordmarkSettle: React.FC<EffectProps> = (p) => {
  const { st, project, duration } = p;
  const f = useCurrentFrame();
  const title = titleOf(project);
  const k = prog(f, 0, 22, ease.outCubic);
  const ctaK = prog(f, 22, 32, ease.outCubic);
  const size = fitFont(title, lerp(k, 150, 110), W - 2 * 96 - [...title].length * lerp(k, 40, 4));
  const settle = lerp(prog(f, 32, duration, ease.linear), 0, -10);
  return (
    <>
      <div style={{ position: "absolute", left: 96, width: W - 192, top: 150, display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${settle}px)` }}>
        <div style={{ position: "absolute", left: "15%", width: "70%", top: -50, height: 260, ...scrim(st, 0.5) }} />
        <div style={{ position: "relative", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: size, lineHeight: 1.1, letterSpacing: lerp(k, 40, 4), color: ink(st), filter: `blur(${(1 - k) * 18}px)`, opacity: Math.min(1, k * 1.5), whiteSpace: "nowrap", textShadow: `0 0 24px ${alpha(st.accent, 0.25 * k)}` }}>{title}</div>
        <div style={{ position: "relative", width: lerp(ctaK, 0, 360), height: 5, background: st.accent, marginTop: 18, borderRadius: 3 }} />
      </div>
      <CtaBlock {...p} k={ctaK} top={CTA_TOP} />
    </>
  );
};
