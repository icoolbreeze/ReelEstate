// Named cursor (collab-cursor-moves · dialogue-duet nameplate) + click payload (input-trigger-moves · cursor-performance).
import React from "react";
import { SANS } from "../fonts";
import { lerp, seg } from "../lib";
import { Easing } from "remotion";

export const NamedCursor: React.FC<{ x: number; y: number; name: string; color: string; lit?: number; o?: number; scale?: number; press?: number }> = ({ x, y, name, color, lit = 1, o = 1, scale = 1, press = 0 }) => (
  <div style={{ position: "absolute", left: x, top: y + 2 * press, opacity: o, transform: `scale(${scale * (1 - 0.2 * press)})`, transformOrigin: "0 0", pointerEvents: "none" }}>
    <svg width={44} height={44} viewBox="0 0 28 28" style={{ position: "absolute", left: -3.2, top: -1.6, filter: "drop-shadow(0 4px 7px rgba(0,0,0,0.38))" }}>
      <path d="M2 1 L2 23 L8 17.5 L11.5 25 L15.5 23.2 L12 15.8 L20 15 Z" fill="#FFFFFF" stroke="#2A2622" strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
    {name && <div style={{
      position: "absolute", left: 30, top: 34, padding: "4px 11px 5px", borderRadius: 8, background: color, color: "#FFF", fontFamily: SANS, fontWeight: 700, fontSize: 17, whiteSpace: "nowrap",
      opacity: 0.28 + 0.72 * lit, filter: `saturate(${0.35 + 0.65 * lit})`, boxShadow: lit > 0.6 ? `0 0 18px ${color}88` : "0 4px 10px rgba(0,0,0,0.2)",
    }}>{name}</div>}
  </div>
);

/** click ripple: expansion out-cubic and fade decoupled (shotcraft input-trigger-moves A).
 *  Reads on any map: thick accent ring sandwiched in white with a dark halo; radius ~110 px on screen (z = parent zoom). */
export const RIPPLE = { dur: 30, grow: 24, r: 110 };
export const Ripple: React.FC<{ f: number; click: number; x: number; y: number; color: string; z?: number }> = ({ f, click, x, y, color, z = 1 }) => {
  if (f < click || f >= click + RIPPLE.dur) return null;
  const d = lerp(24, (2 * RIPPLE.r) / z, seg(f, click, click + RIPPLE.grow, Easing.out(Easing.cubic)));
  const o = 1 - seg(f, click + 10, click + RIPPLE.dur);
  const bw = lerp(12, 6, seg(f, click, click + RIPPLE.grow)) / z;
  const dot = lerp(0.8, 0, seg(f, click, click + 12));
  const ring = (dd: number, w: number, c: string, extra: React.CSSProperties = {}) => (
    <div style={{ position: "absolute", left: x - dd / 2, top: y - dd / 2, width: dd, height: dd, borderRadius: "50%", border: `${w}px solid ${c}`, boxSizing: "border-box", ...extra }} />
  );
  return (
    <div style={{ position: "absolute", left: 0, top: 0, opacity: o, pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: x - 26 / z, top: y - 26 / z, width: 52 / z, height: 52 / z, borderRadius: "50%", background: color, opacity: dot, boxShadow: "0 0 0 3px #FFFFFF" }} />
      {ring(d + 4 * bw, 4 * bw, "rgba(20,18,16,0.35)")}
      {ring(d + 2 * bw, 2 * bw, "#FFFFFF")}
      {ring(d, bw, color)}
    </div>
  );
};

/** cubic bezier with the "wrist flick" overshoot: t runs 0→1.05 by `peak`, then settles to 1 */
export const flickT = (f: number, a: number, peak: number, settle: number) =>
  f < peak ? lerp(0, 1.05, seg(f, a, peak, Easing.out(Easing.cubic))) : lerp(1.05, 1, seg(f, peak, settle, Easing.inOut(Easing.quad)));
export const bez = (p0: number[], p3: number[], t: number, bow = 0.35) => {
  const dx = p3[0] - p0[0], dy = p3[1] - p0[1];
  const p1 = [p0[0] + dx * 0.3 - dy * bow, p0[1] + dy * 0.3 + dx * bow * 0.4];
  const p2 = [p0[0] + dx * 0.85 + dy * bow * 0.3, p0[1] + dy * 0.6 - dx * bow * 0.1];
  const u = 1 - t;
  return [u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0], u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]];
};
