// Data-number + price effects. Motion grammar after video-shotcraft cards odometer-digit-roll,
// counter-confetti (count timing only — no confetti) and outline-word-fill (Apache-2.0).
// Re-skinned to StyleTokens (gold/red/accent, latin/sans fonts).
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { EffectProps } from "./types";
import { alpha, ease, lerp, prog, priceOf, splitNumber } from "./kit";

const W = 1440;
const SPIN = 0.85; // rows per frame while spinning

/** Continuous strip position (rows) for reel i landing on digit d; lock order left→right. */
const reelPos = (f: number, i: number, d: number, start: number): number => {
  const s = start + i * 6;
  const p0 = SPIN * s;
  const T = Math.ceil((p0 + 6 - d) / 10) * 10 + d;
  if (f < s) return SPIN * Math.max(f, 0);
  if (f < s + 14) return lerp(ease.outCubic((f - s) / 14), p0, T + 0.5);
  if (f < s + 20) return lerp(ease.outCubic((f - s - 14) / 6), T + 0.5, T);
  return T;
};

const Odometer: React.FC<{ value: string; st: StyleTokens; size: number; color: string; start?: number }> = ({ value, st, size, color, start = 8 }) => {
  const f = useCurrentFrame();
  const row = Math.round(size * 1.1);
  const dw = Math.round(size * 0.62);
  let di = 0;
  const cells = [...value].map((ch, k) => {
    if (!/\d/.test(ch)) {
      return <div key={k} style={{ height: row, lineHeight: `${row}px`, fontSize: size, fontFamily: st.fonts.latin, fontWeight: 800, color }}>{ch}</div>;
    }
    const i = di++;
    const pos = reelPos(f, i, Number(ch), start);
    const speed = Math.abs(pos - reelPos(f - 1, i, Number(ch), start));
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
  const lockF = start + Math.max(0, di - 1) * 6 + 20;
  const pulse = prog(f, lockF, lockF + 4) * (1 - prog(f, lockF + 4, lockF + 10));
  return <div style={{ display: "flex", alignItems: "center", transform: `scale(${1 + 0.035 * pulse})` }}>{cells}</div>;
};

const Caption: React.FC<{ text?: string; st: StyleTokens; at: number }> = ({ text, st, at }) => {
  const f = useCurrentFrame();
  if (!text) return null;
  const k = prog(f, at, at + st.enterFrames, ease.outCubic);
  return <div style={{ marginTop: 14, opacity: k, transform: `translateY(${lerp(k, 12, 0)}px)`, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 34, color: st.text, textShadow: st.textGlow, textAlign: "center", maxWidth: 1100 }}>{text}</div>;
};

const specValue = (p: EffectProps) => {
  const title = p.shot.spec?.title ?? p.shot.number?.value ?? String(p.project.property.area.value);
  const { num, rest } = splitNumber(title);
  return { num: num || title, rest, lines: p.shot.spec?.lines ?? [] };
};

/** odometer-digit-roll for a spec number (area etc.): reels spin, lock left→right with overshoot, one pulse. */
export const OdometerRoll: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const v = specValue(p);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: 300, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16 }}>
        <Odometer value={v.num} st={st} size={170} color={st.gold} />
        {v.rest ? <div style={{ fontFamily: st.fonts.latin, fontWeight: 700, fontSize: 64, color: st.text, paddingBottom: 26 }}>{v.rest}</div> : null}
      </div>
      <Caption text={v.lines.slice(0, 3).join("  ·  ")} st={st} at={44} />
    </div>
  );
};

/** count-up: number eases (outQuart) from 0 with a small scale overshoot as it lands; no particles. */
export const CountUp: React.FC<EffectProps> = (p) => {
  const { st } = p;
  const f = useCurrentFrame();
  const v = specValue(p);
  const target = Number(v.num.replace(/,/g, "")) || 0;
  const decimals = (v.num.split(".")[1] ?? "").length;
  const k = prog(f, 4, 40, ease.outQuart);
  const cur = (target * k).toFixed(decimals);
  const shown = v.num.includes(",") ? Number(cur).toLocaleString("en-US", { minimumFractionDigits: decimals }) : cur;
  const land = prog(f, 36, 42) * (1 - prog(f, 42, 50));
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: 300, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, transform: `scale(${1 + 0.06 * land})` }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 180, lineHeight: 1, color: st.gold, fontVariantNumeric: "tabular-nums", textShadow: `0 0 24px ${alpha(st.gold, 0.45)}` }}>{shown}</div>
        {v.rest ? <div style={{ fontFamily: st.fonts.latin, fontWeight: 700, fontSize: 64, color: st.text, paddingBottom: 18 }}>{v.rest}</div> : null}
      </div>
      <div style={{ width: lerp(prog(f, 30, 44, ease.outCubic), 0, 520), height: 6, background: st.accent, marginTop: 18, borderRadius: 3 }} />
      <Caption text={v.lines.slice(0, 3).join("  ·  ")} st={st} at={40} />
    </div>
  );
};

/** Price variant of the odometer (gold, or red when over the limit). */
export const PriceOdometer: React.FC<EffectProps> = (p) => {
  const { st, shot, project } = p;
  const pr = priceOf(project, shot);
  const color = shot.number?.over ? st.red : st.gold;
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: 320, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 18 }}>
        <Odometer value={pr.value} st={st} size={160} color={color} start={6} />
        <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 44, color: st.text, paddingBottom: 28 }}>{pr.unit}</div>
      </div>
      <Caption text={pr.caption} st={st} at={40} />
    </div>
  );
};

/** outline-word-fill for price: hollow outline number snaps down from 3.2x, dashed ring closes in, then fills with the accent. */
export const PricePop: React.FC<EffectProps> = (p) => {
  const { st, shot, project } = p;
  const f = useCurrentFrame();
  const pr = priceOf(project, shot);
  const color = shot.number?.over ? st.red : st.gold;
  const s = lerp(prog(f, 0, 14, ease.outExpo), 3.2, 1);
  const fill = prog(f, 16, 20);
  const ring = lerp(prog(f, 10, 28, ease.outCubic), 2.8, 1);
  const ringOp = prog(f, 10, 16) * (1 - prog(f, 40, 52));
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: 300, height: 360, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", left: W / 2 - 260, top: 20, width: 520, height: 260, borderRadius: "50%", border: `3px dashed ${alpha(st.accent, 0.8)}`, transform: `scale(${ring}) rotate(${f * 0.6}deg)`, opacity: ringOp }} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, transform: `scale(${s})` }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 170, lineHeight: 1, color: fill > 0.5 ? color : "transparent", WebkitTextStroke: `2px ${fill > 0.5 ? color : st.text}`, textShadow: fill > 0.5 ? `0 0 26px ${alpha(color, 0.5)}` : undefined }}>{pr.value}</div>
        <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 44, color: st.text, paddingBottom: 22, opacity: fill }}>{pr.unit}</div>
      </div>
      <Caption text={pr.caption} st={st} at={26} />
    </div>
  );
};
