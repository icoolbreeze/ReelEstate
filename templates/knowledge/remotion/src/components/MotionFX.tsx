// MotionFX — custom motion layer for the knowledge series v4b (purple / off-white / yellow).
// Kinetic typography, 3D card flips, light sweeps, drifting particles, glow counters, segment wipes,
// and the whole-Chengdu dense store map. Deterministic (frame-driven only).
// RULE: never render internal file names / paths / source labels on screen.
import React from "react";
import { AbsoluteFill, Img, random, staticFile, useCurrentFrame } from "remotion";
import { NUM, SANS, TITLE } from "../fonts";
import { E_OUT, backLite, lerp, seg } from "../lib";
import { C } from "./MotionV3";
import DOTS from "../episode/mapdots.json";

export const W = 1440, H = 1080;

// ---------- floating particles (purple + yellow bokeh), parallax depth ----------
export const Particles: React.FC<{ n?: number; seed?: string; opacity?: number }> = ({ n = 28, seed = "p", opacity = 1 }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      {Array.from({ length: n }).map((_, i) => {
        const z = 0.3 + random(`${seed}z${i}`) * 0.9;
        const x0 = random(`${seed}x${i}`) * W, y0 = random(`${seed}y${i}`) * H;
        const r = 4 + z * 14;
        const x = (x0 + f * 0.6 * z + Math.sin(f / 40 + i) * 18) % (W + 40) - 20;
        const y = (y0 - f * 0.9 * z + H * 4) % (H + 40) - 20;
        const yel = random(`${seed}c${i}`) > 0.62;
        const col = yel ? "255,200,61" : "109,59,235";
        return <div key={i} style={{ position: "absolute", left: x, top: y, width: r, height: r, borderRadius: r, background: `radial-gradient(circle, rgba(${col},${0.5 * z}) 0%, rgba(${col},0) 70%)`, filter: `blur(${(1 - z) * 2}px)` }} />;
      })}
    </AbsoluteFill>
  );
};

// ---------- diagonal light sweep across a card / the frame ----------
export const LightSweep: React.FC<{ local: number; start: number; dur?: number; width?: number; strength?: number }> = ({ local, start, dur = 22, width = 220, strength = 0.55 }) => {
  const p = seg(local, start, start + dur);
  if (p <= 0 || p >= 1) return null;
  const x = lerp(-width - 300, W + 300, p);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden", mixBlendMode: "screen" }}>
      <div style={{ position: "absolute", top: -300, left: x, width, height: H + 600, transform: "rotate(18deg)", background: `linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,240,200,${strength}) 50%, rgba(255,255,255,0) 100%)` }} />
    </AbsoluteFill>
  );
};

// ---------- kinetic typography: per-character rise + rotateX settle, yellow underline wipe ----------
export const KineticText: React.FC<{ text: string; local: number; start: number; size?: number; color?: string; stagger?: number; underline?: boolean; font?: string; weight?: number }> = ({ text, local, start, size = 84, color = C.ink, stagger = 2, underline = false, font = TITLE, weight = 700 }) => {
  const chars = Array.from(text);
  const endAt = start + chars.length * stagger + 10;
  return (
    <span style={{ position: "relative", display: "inline-block", perspective: 800, whiteSpace: "nowrap" }}>
      {chars.map((ch, i) => {
        const q = seg(local, start + i * stagger, start + i * stagger + 12, E_OUT);
        return <span key={i} style={{ display: "inline-block", fontFamily: font, fontWeight: weight, fontSize: size, lineHeight: 1.1, color, opacity: q, transform: `translateY(${lerp(size * 0.6, 0, q)}px) rotateX(${lerp(-80, 0, q)}deg)`, transformOrigin: "50% 100%" }}>{ch === " " ? "\u00A0" : ch}</span>;
      })}
      {underline && <span style={{ position: "absolute", left: 0, bottom: -size * 0.04, height: size * 0.16, width: `${seg(local, endAt - 6, endAt + 10, E_OUT) * 100}%`, background: C.yellow, zIndex: -1, borderRadius: 4 }} />}
    </span>
  );
};

// ---------- 3D card flip-in (rotateY) ----------
export const Flip3D: React.FC<{ local: number; start: number; dur?: number; axis?: "X" | "Y"; children: React.ReactNode; style?: React.CSSProperties }> = ({ local, start, dur = 16, axis = "Y", children, style }) => {
  const q = seg(local, start, start + dur, E_OUT);
  const s = backLite(seg(local, start, start + dur + 2));
  return (
    <div style={{ perspective: 1400, ...style }}>
      <div style={{ opacity: Math.min(1, q * 2), transform: `rotate${axis}(${lerp(axis === "Y" ? -95 : 85, 0, q)}deg) scale(${lerp(0.9, 1, s)})`, transformOrigin: axis === "Y" ? "0% 50%" : "50% 0%", backfaceVisibility: "hidden" }}>{children}</div>
    </div>
  );
};

// ---------- glow counter (Barlow Condensed, yellow glow) ----------
export const GlowCounter: React.FC<{ value: number; suffix?: string; local: number; start: number; dur?: number; size?: number; color?: string; dec?: number }> = ({ value, suffix = "", local, start, dur = 30, size = 150, color = C.blue, dec = 0 }) => {
  const p = seg(local, start, start + dur, E_OUT);
  const pulse = 1 + 0.04 * Math.sin(seg(local, start + dur, start + dur + 12) * Math.PI);
  const glow = 0.35 + 0.65 * seg(local, start + dur - 6, start + dur + 6);
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", transform: `scale(${pulse})`, transformOrigin: "50% 80%" }}>
      <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: size, lineHeight: 1, color, fontVariantNumeric: "tabular-nums", textShadow: `0 0 ${24 * glow}px rgba(255,200,61,${0.85 * glow}), 0 0 ${60 * glow}px rgba(109,59,235,${0.45 * glow})` }}>{(value * p).toFixed(dec)}</span>
      {suffix && <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: size * 0.42, color: C.blueDeep, marginLeft: 6 }}>{suffix}</span>}
    </span>
  );
};

// ---------- segment wipe: purple slab + yellow edge sweeps off, revealing the new scene ----------
export const SegWipe: React.FC<{ dir?: 1 | -1 }> = ({ dir = 1 }) => {
  const f = useCurrentFrame();
  const p = seg(f, 0, 14, E_OUT);
  if (p >= 1) return null;
  const off = p * (W + 500);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: -200, height: H + 400, width: W + 200, left: dir > 0 ? off - 100 : -off - 100, transform: "skewX(-14deg)", background: `linear-gradient(90deg, ${C.blueDeep} 0%, ${C.blue} 92%, ${C.yellow} 92%, ${C.yellow} 100%)` }} />
    </AbsoluteFill>
  );
};

// ---------- whole-Chengdu dense store map (real Amap POI, projected onto the base) ----------
type Dot = { b: string; x: number; y: number };
const D = DOTS as unknown as { base: string; w: number; h: number; brands: { name: string; color: string; n: number }[]; dots: Dot[]; total: number };
export const DenseMap: React.FC<{ local: number; brandAt: Record<string, number>; focusAt?: number; focusBrand?: string; countTo?: number }> = ({ local, brandAt, focusAt = 1e9, focusBrand = "德佑" }) => {
  const sc = Math.max(W / D.w, H / D.h);
  const ox = (W - D.w * sc) / 2, oy = (H - D.h * sc) / 2;
  const zoom = lerp(1.12, 1.0, seg(local, 0, 40, E_OUT)) * lerp(1, 1.06, seg(local, 40, 400));
  const focus = seg(local, focusAt, focusAt + 14, E_OUT);
  let shown = 0;
  const byB: Record<string, number> = {};
  for (const d of D.dots) {
    const st = brandAt[d.b] ?? 0;
    const idx = (byB[d.b] = (byB[d.b] ?? 0) + 1);
    if (local >= st + Math.min(26, idx * 0.25)) shown++;
  }
  const seen: Record<string, number> = {};
  return (
    <AbsoluteFill style={{ background: C.paper, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${zoom})`, transformOrigin: "52% 50%" }}>
        <Img src={staticFile(D.base)} style={{ position: "absolute", left: ox, top: oy, width: D.w * sc, height: D.h * sc }} />
        {D.dots.map((d, i) => {
          const st = brandAt[d.b] ?? 0;
          const k = (seen[d.b] = (seen[d.b] ?? 0) + 1);
          const t0 = st + Math.min(26, k * 0.25);
          const q = seg(local, t0, t0 + 6, E_OUT);
          if (q <= 0) return null;
          const col = D.brands.find((b) => b.name === d.b)?.color ?? C.blue;
          const dim = focus > 0 && d.b !== focusBrand ? lerp(1, 0.18, focus) : 1;
          const big = focus > 0 && d.b === focusBrand ? lerp(1, 1.5, focus) : 1;
          const r = 9 * big;
          const ring = seg(local, t0, t0 + 14);
          return (
            <React.Fragment key={i}>
              {ring < 1 && <div style={{ position: "absolute", left: ox + d.x * sc - 14, top: oy + d.y * sc - 14, width: 28, height: 28, borderRadius: 14, border: `2px solid ${col}`, opacity: (1 - ring) * 0.8, transform: `scale(${lerp(0.4, 1.6, ring)})` }} />}
              <div style={{ position: "absolute", left: ox + d.x * sc - r / 2, top: oy + d.y * sc - r / 2, width: r, height: r, borderRadius: r, background: col, border: d.b === "中环" ? "2px solid #FFFFFF" : "1.5px solid rgba(255,255,255,0.9)", boxShadow: d.b === "中环" ? "0 0 8px rgba(255,200,61,0.9)" : `0 0 6px ${col}`, opacity: q * dim, transform: `scale(${lerp(2.2, 1, q)})` }} />
            </React.Fragment>
          );
        })}
      </AbsoluteFill>
      <Particles n={14} seed="map" opacity={0.5} />
      {/* title + live counter */}
      <div style={{ position: "absolute", left: 64, top: 96, background: "rgba(251,248,241,0.94)", borderRadius: 20, padding: "16px 26px 18px", boxShadow: "0 18px 44px rgba(36,23,63,0.16)", opacity: seg(local, 2, 12, E_OUT), transform: `translateY(${lerp(-20, 0, seg(local, 2, 12, E_OUT))}px)` }}>
        <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 40, color: C.ink }}>成都 贝壳平台品牌门店</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 4 }}>
          <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 84, color: C.blue, lineHeight: 1, textShadow: "0 0 20px rgba(255,200,61,0.7)", fontVariantNumeric: "tabular-nums" }}>{shown}</span>
          <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 26, color: C.ink }}>家门店已标注</span>
        </div>
        <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 17, color: C.sub, marginTop: 2 }}>高德公开 POI 检索 全市各区县 部分收录</div>
      </div>
      {/* legend with per-brand counts */}
      <div style={{ position: "absolute", left: 0, width: W, top: 300 + 0, display: "none" }} />
      <div style={{ position: "absolute", right: 56, top: 96, display: "flex", flexDirection: "column", gap: 10 }}>
        {D.brands.map((b) => {
          const st = brandAt[b.name] ?? 0;
          const q = seg(local, st, st + 10, E_OUT);
          const n = Math.round(b.n * seg(local, st, st + 26));
          const on = focus > 0 ? b.name === focusBrand : true;
          return (
            <div key={b.name} style={{ display: "flex", alignItems: "center", gap: 12, background: "rgba(251,248,241,0.94)", borderRadius: 999, padding: "8px 20px 8px 14px", boxShadow: "0 8px 22px rgba(36,23,63,0.14)", opacity: q * (on ? 1 : 0.45), transform: `translateX(${lerp(60, 0, q)}px) scale(${on && focus > 0 ? lerp(1, 1.12, focus) : 1})`, transformOrigin: "100% 50%" }}>
              <span style={{ width: 18, height: 18, borderRadius: 9, background: b.color, border: b.name === "中环" ? "2px solid #FFC83D" : "none", boxSizing: "border-box" }} />
              <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 25, color: C.ink, minWidth: 74 }}>{b.name}</span>
              <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 30, color: C.blueDeep, minWidth: 48, textAlign: "right" }}>{n}</span>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", right: 24, bottom: 92, fontFamily: SANS, fontWeight: 500, fontSize: 14, color: "rgba(36,23,63,0.75)", background: "rgba(251,248,241,0.86)", padding: "3px 10px 4px", borderRadius: 6 }}>地图数据 © 高德地图</div>
    </AbsoluteFill>
  );
};

// ---------- 德佑 1000+ hero card over the dimmed map ----------
export const HeroFact: React.FC<{ local: number; start: number }> = ({ local, start }) => {
  const q = seg(local, start, start + 12, E_OUT);
  if (q <= 0) return null;
  return (
    <AbsoluteFill style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Flip3D local={local} start={start} axis="X">
        <div style={{ position: "relative", overflow: "hidden", background: "linear-gradient(135deg,#FFFFFF 0%,#FBF8F1 100%)", borderRadius: 30, padding: "34px 64px 38px", boxShadow: "0 40px 90px rgba(36,23,63,0.35)", border: `3px solid ${C.yellow}`, textAlign: "center", marginTop: 40 }}>
          <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 44, color: C.ink }}>光德佑 在成都就有</div>
          <div style={{ marginTop: 6 }}><GlowCounter value={1000} suffix="+ 家门店" local={local} start={start + 8} dur={26} size={170} /></div>
          <LightSweep local={local} start={start + 30} dur={20} width={160} />
        </div>
      </Flip3D>
    </AbsoluteFill>
  );
};
