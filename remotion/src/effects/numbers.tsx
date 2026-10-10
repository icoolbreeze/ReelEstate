// Data-number + price effects. Motion grammar after video-shotcraft cards odometer-digit-roll,
// counter-confetti (count timing only; no confetti) and outline-word-fill (Apache-2.0).
// Re-skinned to StyleTokens (gold/red/accent, latin/sans fonts). video-taste: detail lines are
// label-family chips (no middle-dot chains), block stays above the caption band / PiP.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { EffectProps } from "./types";
import { alpha, bottomLimit, chip, clean, dotLines, ease, fitFont, ink, lerp, prog, priceOf, scrim, splitNumber, type Zones } from "./kit";

const W = 1440;
const SPIN = 0.85; // rows per frame while spinning

/** Top y for a centred block of height h that must end above the caption band and clear the PiP. */
const placeTop = (z: Zones, want: number, h: number, width = 1000) => Math.min(want, bottomLimit(z, (W - width) / 2, (W + width) / 2) - h);

/** Continuous strip position (rows) for reel i landing on digit d; lock order left→right. */
const reelPos = (f: number, i: number, d: number, start: number, stagger = 6, settle = 20): number => {
  const s = start + i * stagger;
  const p0 = SPIN * s;
  const T = Math.ceil((p0 + 6 - d) / 10) * 10 + d;
  const brake = Math.round(settle * 0.7);
  const rest = settle - brake;
  if (f < s) return SPIN * Math.max(f, 0);
  if (f < s + brake) return lerp(ease.outCubic((f - s) / Math.max(1, brake)), p0, T + 0.5);
  if (f < s + settle) return lerp(ease.outCubic((f - s - brake) / Math.max(1, rest)), T + 0.5, T);
  return T;
};

export const Odometer: React.FC<{
  value: string; st: StyleTokens; size: number; color: string;
  start?: number; stagger?: number; settle?: number;
}> = ({ value, st, size, color, start = 8, stagger = 6, settle = 20 }) => {
  const f = useCurrentFrame();
  const row = Math.round(size * 1.1);
  const dw = Math.round(size * 0.62);
  let di = 0;
  const cells = [...value].map((ch, k) => {
    if (!/\d/.test(ch)) {
      return <div key={k} style={{ height: row, lineHeight: `${row}px`, fontSize: size, fontFamily: st.fonts.latin, fontWeight: 800, color }}>{ch}</div>;
    }
    const i = di++;
    const pos = reelPos(f, i, Number(ch), start, stagger, settle);
    const speed = Math.abs(pos - reelPos(f - 1, i, Number(ch), start, stagger, settle));
    const ghost = Math.min(1, Math.max(0, (speed - 0.06) / 0.44));
    const strip = (dy: number, op: number) => (
      <div style={{ position: "absolute", left: 0, top: 0, width: dw, transform: `translateY(${-(pos % 10) * row + dy}px)`, opacity: op }}>
        {Array.from({ length: 20 }, (_, n) => (
          <div key={n} style={{ height: row, lineHeight: `${row}px`, textAlign: "center", fontSize: size, fontWeight: 800, fontFamily: st.fonts.latin, fontVariantNumeric: "tabular-nums", color }}>{n % 10}</div>
        ))}
      </div>
    );
    return (
      <div key={k} style={{ position: "relative", width: dw, height: row, overflow: "hidden" }}>
        {ghost > 0.01 ? strip(row * 0.5, 0.25 * ghost) : null}
        {ghost > 0.01 ? strip(-row * 0.5, 0.12 * ghost) : null}
        {strip(0, 1)}
      </div>
    );
  });
  const lockF = start + Math.max(0, di - 1) * stagger + settle;
  const pulse = prog(f, lockF, lockF + 4) * (1 - prog(f, lockF + 4, lockF + 10));
  return <div style={{ display: "flex", alignItems: "center", transform: `scale(${1 + 0.035 * pulse})` }}>{cells}</div>;
};

/** Detail lines as one row of label-family chips (wraps; each chip ≤1 middle dot). */
const Chips: React.FC<{ lines: string[]; st: StyleTokens; at: number }> = ({ lines, st, at }) => {
  const f = useCurrentFrame();
  if (!lines.length) return null;
  const k = prog(f, at, at + st.enterFrames, ease.outCubic);
  return (
    <div style={{ marginTop: 18, display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 12, maxWidth: 1150, opacity: k, transform: `translateY(${lerp(k, 12, 0)}px)` }}>
      {lines.map((l) => (
        <span key={l} style={{ ...chip(st), fontFamily: st.fonts.sans, fontWeight: 700, fontSize: fitFont(l, 30, 540, 22), color: ink(st) }}>{l}</span>
      ))}
    </div>
  );
};

/** Slow settle drift once the number has landed, so the hold is never a frozen frame. */
const drift = (f: number, from: number, duration: number) => lerp(prog(f, from, Math.max(from + 1, duration), ease.linear), 0, -10);

const specValue = (p: EffectProps) => {
  const title = clean(p.shot.spec?.title ?? p.shot.number?.value ?? String(p.project.property.area.value));
  const { num, rest } = splitNumber(title);
  return { num: num || title, rest, lines: (p.shot.spec?.lines ?? []).slice(0, 3).flatMap(dotLines) };
};

/** odometer-digit-roll for a spec number (area etc.): reels spin, lock left→right with overshoot, one pulse. */
export const OdometerRoll: React.FC<EffectProps> = (p) => {
  const { st, zones, duration } = p;
  const f = useCurrentFrame();
  const v = specValue(p);
  const top = placeTop(zones, 280, 187 + 18 + Math.ceil(v.lines.length / 2) * 56);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top, display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${drift(f, 60, duration)}px)` }}>
      <div style={{ position: "absolute", left: 220, right: 220, top: -40, height: 280, ...scrim(st, 0.45) }} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16 }}>
        <Odometer value={v.num} st={st} size={170} color={st.gold} />
        {v.rest ? <div style={{ fontFamily: st.fonts.latin, fontWeight: 700, fontSize: 64, color: ink(st), paddingBottom: 26 }}>{v.rest}</div> : null}
      </div>
      <Chips lines={v.lines} st={st} at={44} />
    </div>
  );
};

/** count-up: number eases (outQuart) from 0 with a small scale overshoot as it lands; no particles. */
export const CountUp: React.FC<EffectProps> = (p) => {
  const { st, zones, duration } = p;
  const f = useCurrentFrame();
  const v = specValue(p);
  const target = Number(v.num.replace(/,/g, "")) || 0;
  const decimals = (v.num.split(".")[1] ?? "").length;
  const k = prog(f, 4, 40, ease.outQuart);
  const cur = (target * k).toFixed(decimals);
  const shown = v.num.includes(",") ? Number(cur).toLocaleString("en-US", { minimumFractionDigits: decimals }) : cur;
  const land = prog(f, 36, 42) * (1 - prog(f, 42, 50));
  const top = placeTop(zones, 280, 180 + 24 + 18 + Math.ceil(v.lines.length / 2) * 56);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top, display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${drift(f, 56, duration)}px)` }}>
      <div style={{ position: "absolute", left: 220, right: 220, top: -40, height: 280, ...scrim(st, 0.45) }} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, transform: `scale(${1 + 0.06 * land})` }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 180, lineHeight: 1, color: st.gold, fontVariantNumeric: "tabular-nums", textShadow: `0 0 24px ${alpha(st.gold, 0.35)}` }}>{shown}</div>
        {v.rest ? <div style={{ fontFamily: st.fonts.latin, fontWeight: 700, fontSize: 64, color: ink(st), paddingBottom: 18 }}>{v.rest}</div> : null}
      </div>
      <div style={{ width: lerp(prog(f, 30, 42, ease.outCubic), 0, 520), height: 6, background: st.accent, marginTop: 18, borderRadius: 3 }} />
      <Chips lines={v.lines} st={st} at={40} />
    </div>
  );
};

/** Price variant of the odometer (gold, or red when over the limit). */
export const PriceOdometer: React.FC<EffectProps> = (p) => {
  const { st, shot, project, zones, duration } = p;
  const f = useCurrentFrame();
  const pr = priceOf(project, shot);
  const color = shot.number?.over ? st.red : st.gold;
  const lines = pr.caption ? dotLines(pr.caption) : [];
  const top = placeTop(zones, 300, 176 + 18 + lines.length * 56);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top, display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${drift(f, 60, duration)}px)` }}>
      <div style={{ position: "absolute", left: 220, right: 220, top: -40, height: 280, ...scrim(st, 0.45) }} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 18 }}>
        <Odometer value={pr.value} st={st} size={160} color={color} start={6} />
        <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 44, color: ink(st), paddingBottom: 28 }}>{pr.unit}</div>
      </div>
      <Chips lines={lines} st={st} at={40} />
    </div>
  );
};

/** outline-word-fill for price: hollow outline number snaps down from 3.2x, dashed ring closes in, then fills with the accent. */
export const PricePop: React.FC<EffectProps> = (p) => {
  const { st, shot, project, zones, duration } = p;
  const f = useCurrentFrame();
  const pr = priceOf(project, shot);
  const color = shot.number?.over ? st.red : st.gold;
  const lines = pr.caption ? dotLines(pr.caption) : [];
  const s = lerp(prog(f, 0, 14, ease.outExpo), 3.2, 1);
  const fill = prog(f, 16, 20);
  const ring = lerp(prog(f, 10, 28, ease.outCubic), 2.8, 1);
  const ringOp = prog(f, 10, 16) * (1 - prog(f, 34, 44));
  const top = placeTop(zones, 300, 190 + 18 + lines.length * 56);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top, display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${drift(f, 44, duration)}px)` }}>
      <div style={{ position: "absolute", left: 220, right: 220, top: -40, height: 280, ...scrim(st, 0.45) }} />
      <div style={{ position: "absolute", left: W / 2 - 260, top: -30, width: 520, height: 250, borderRadius: "50%", border: `3px dashed ${alpha(st.accent, 0.8)}`, transform: `scale(${ring})`, opacity: ringOp }} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, transform: `scale(${s})` }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 170, lineHeight: 1, fontVariantNumeric: "tabular-nums", color: fill > 0.5 ? color : "transparent", WebkitTextStroke: `2px ${fill > 0.5 ? color : ink(st)}`, textShadow: fill > 0.5 ? `0 0 22px ${alpha(color, 0.35)}` : undefined }}>{pr.value}</div>
        <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 44, color: ink(st), paddingBottom: 22, opacity: fill }}>{pr.unit}</div>
      </div>
      <Chips lines={lines} st={st} at={26} />
    </div>
  );
};
