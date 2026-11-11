// Hand-drawn marker underline, ported verbatim from ep01 (projects/knowledge/ep01-intro/jobs/v5_stills/src/components/Shotcraft.tsx,
// "typography/marker-underline-title"): seeded wobbly filled stroke, clip-revealed left->right with an ease-out draw-on.
import React, { useId } from "react";
import { interpolate } from "remotion";
const sg = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const mulberry32 = (a: number) => () => { let t = (a += 0x6d2b79f5); t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const buildStroke = (len: number, seed: number) => {
  const r = mulberry32(seed); const N = 40; const top: string[] = []; const bot: string[] = [];
  const wob = Array.from({ length: N + 1 }, () => r() - 0.5);
  for (let i = 0; i <= N; i++) {
    const t = i / N; const x = t * len;
    const mid = 19 - t * 9 + Math.sin(t * Math.PI * 1.6 + 0.4) * 2.6 + wob[i] * 1.6;
    const w = Math.max(2.2, 14 + Math.sin(t * Math.PI) * 6 - Math.max(0, t - 0.86) * 46 + wob[i] * 3);
    top.push(`${x.toFixed(1)},${(mid - w / 2).toFixed(1)}`); bot.push(`${x.toFixed(1)},${(mid + w / 2).toFixed(1)}`);
  }
  return `M${top.join("L")}L${bot.reverse().join("L")}Z`;
};
export const MarkerUnderline: React.FC<{ len: number; local: number; start: number; color?: string; seed?: number; style?: React.CSSProperties }> = ({ len, local, start, color = "#E8202A", seed = 77, style }) => {
  const id = `mu-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const d = 1 - Math.pow(1 - sg(local, start, start + 10), 2.2);
  return (
    <svg width={len} height={44} viewBox={`0 0 ${len} 44`} style={{ position: "absolute", overflow: "visible", ...style }}>
      <defs><clipPath id={id}><rect x={0} y={-20} width={d * (len + 6)} height={60} /></clipPath></defs>
      {d > 0 && <path d={buildStroke(len, seed)} fill={color} clipPath={`url(#${id})`} />}
    </svg>
  );
};
