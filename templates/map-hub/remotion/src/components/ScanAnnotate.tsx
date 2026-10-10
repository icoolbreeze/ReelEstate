// scanline-annotate-focus for footage (shotcraft references/shots/effects/scanline-annotate-focus.md), driven by per-clip JSON.
//  - a light scan line sweeps top→bottom at constant speed (zero easing); a target fires when the line crosses its box BOTTOM
//    (ft = start + (bottom+30)/(H+60)·dur), min 3 f apart, sorted by y
//  - corner viewfinder 1.75→1 (backLite ≤4% overshoot, 7 f), focus flash ≤0.07, label 2 f after the box (box settles, then it is named)
//  - status line counts fired targets live: SCAN 0n/0N → ANALYSIS · COMPLETE
//  - after firing, boxes FOLLOW the tracked keyframes (annotations/<ID>.json from pipeline/track_annotations.py)
// Annotation JSON: { space: "video"|"image"|"frame", size?: [w,h], targets: [{ id, label, sub, kf: [[t_sec, x, y, w, h], ...] }] }  (x,y,w,h normalised 0–1)
import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, staticFile } from "remotion";
import { NUM, SANS } from "../fonts";
import { backLite, H, lerp, seg, W, E_OUT } from "../lib";

export type Footage = { kind: "video" | "image" | "pending"; src?: string; still?: string; cx?: number; w?: number; h?: number; fps?: number; dur?: number; status: string; purpose?: string; label?: string; kb?: { s0: number; s1: number; ox0: number; oy0: number; ox1: number; oy1: number } };
export type Target = { id: string; label: string; sub?: string; kf: number[][] };
export type Ann = { space: "video" | "image" | "frame"; method?: string; targets: Target[] };

const FPS = 30;
/** media → frame mapping (cover fit + optional Ken Burns); returns a function (u,v) normalised media coords → frame px */
export const mediaGeom = (fo: Footage, local: number) => {
  const w = fo.w ?? W, h = fo.h ?? H;
  const c = Math.max(W / w, H / h), dw = w * c, dh = h * c, oy = (H - dh) / 2;
  const ox = Math.min(0, Math.max(W - dw, W / 2 - (fo.cx ?? 0.5) * dw));   // cx: horizontal crop centre (face) for 16:9 → 4:3
  const kb = fo.kind === "image" ? fo.kb : undefined;
  const p = seg(local, 0, 300);
  const s = kb ? lerp(kb.s0, kb.s1, p) : 1;
  const Ox = kb ? lerp(kb.ox0, kb.ox1, p) * W : W / 2, Oy = kb ? lerp(kb.oy0, kb.oy1, p) * H : H / 2;
  return { s, Ox, Oy, dw, dh, ox, oy, map: (u: number, v: number) => [Ox + (ox + u * dw - Ox) * s, Oy + (oy + v * dh - Oy) * s] };
};

const sampleKf = (kf: number[][], t: number) => {
  if (!kf.length) return null;
  if (t <= kf[0][0]) return kf[0].slice(1);
  for (let i = 1; i < kf.length; i++) {
    if (t <= kf[i][0]) { const a = kf[i - 1], b = kf[i], u = (t - a[0]) / Math.max(1e-6, b[0] - a[0]); return a.slice(1).map((v, k) => lerp(v, b[k + 1], u)); }
  }
  return kf[kf.length - 1].slice(1);
};

/** the clip picture itself (video, Ken Burns still, or a labelled pending card) */
export const ClipMedia: React.FC<{ fo: Footage; id: string; local: number; inFrame?: number; grade?: string; transparent?: boolean }> = ({ fo, id, local, inFrame = 12, grade, transparent }) => {
  if (fo.kind === "pending") {
    return (
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 40%, #3A3631 0%, #1E1C19 75%)", alignItems: "center", justifyContent: "center", fontFamily: SANS }}>
        <div style={{ textAlign: "center", color: "#EFECE6" }}>
          <div style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 64, letterSpacing: 2, opacity: 0.9 }}>{id}</div>
          <div style={{ fontSize: 30, fontWeight: 700, marginTop: 8 }}>{fo.purpose}</div>
          <div style={{ fontSize: 20, fontWeight: 500, marginTop: 14, opacity: 0.6, letterSpacing: 2 }}>Muse 素材待生成 · 占位画面</div>
        </div>
      </AbsoluteFill>
    );
  }
  const g = mediaGeom(fo, local);
  const style: React.CSSProperties = { position: "absolute", left: g.ox, top: g.oy, width: g.dw, height: g.dh, filter: grade };
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: transparent ? undefined : "#111" }}>
      <AbsoluteFill style={{ transform: `scale(${g.s})`, transformOrigin: `${g.Ox}px ${g.Oy}px` }}>
        {fo.kind === "image" ? <Img src={staticFile(fo.src!)} style={{ ...style, objectFit: "cover" }} />
          : <OffthreadVideo src={staticFile(fo.src!)} muted transparent={transparent} startFrom={inFrame} style={{ ...style, objectFit: "cover" }} />}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Corners: React.FC<{ x: number; y: number; w: number; h: number; s: number; o: number; flash: number }> = ({ x, y, w, h, s, o, flash }) => {
  const arm = Math.max(12, Math.min(26, Math.min(w, h) / 3.2)), b = "2.5px solid #FFFFFF", pad = 8;
  const cs: React.CSSProperties[] = [
    { left: 0, top: 0, borderTop: b, borderLeft: b }, { right: 0, top: 0, borderTop: b, borderRight: b },
    { left: 0, bottom: 0, borderBottom: b, borderLeft: b }, { right: 0, bottom: 0, borderBottom: b, borderRight: b },
  ];
  return (
    <div style={{ position: "absolute", left: x - pad, top: y - pad, width: w + 2 * pad, height: h + 2 * pad, opacity: o, transform: `scale(${s})`, filter: "drop-shadow(0 1px 3px rgba(0,0,0,0.45))" }}>
      {cs.map((c, i) => <div key={i} style={{ position: "absolute", width: arm, height: arm, ...c }} />)}
      <div style={{ position: "absolute", inset: pad, background: "#FFFFFF", opacity: flash }} />
    </div>
  );
};

/** overlay: scan line + tracked viewfinders + labels + status counter. local = frames since the clip is on screen. */
// mediaOffset = frames the clip has already been playing when the overlay's local 0 starts (overlay starts after the open move)
export const ScanAnnotate: React.FC<{ fo: Footage; ann?: Ann; local: number; inFrame?: number; mediaOffset?: number; scanStart?: number; scanDur?: number; showLine?: boolean; outAt?: number }> = ({ fo, ann, local, inFrame = 12, mediaOffset = 0, scanStart = 5, scanDur = 24, showLine = true, outAt = 1e9 }) => {
  if (!ann || !ann.targets.length) return null;
  const g = mediaGeom(fo, local);
  // <OffthreadVideo startFrom> counts composition frames and plays in real time, so clip time = (inFrame + frames played) / 30
  // regardless of the source fps (Muse clips are 24 fps); keyframes are in clip seconds.
  const tSec = (fr: number) => (fo.kind === "video" ? (inFrame + mediaOffset + fr) / FPS : (mediaOffset + fr) / FPS);
  const boxAt = (t: Target, fr: number) => {
    const b = sampleKf(t.kf, tSec(fr));
    if (!b) return null;
    if (ann.space === "frame") return { x: b[0] * W, y: b[1] * H, w: b[2] * W, h: b[3] * H };
    const [x0, y0] = g.map(b[0], b[1]), [x1, y1] = g.map(b[0] + b[2], b[1] + b[3]);
    return { x: Math.max(0, x0), y: Math.max(0, y0), w: Math.min(W, x1) - Math.max(0, x0), h: Math.min(H, y1) - Math.max(0, y0) };
  };
  // trigger frames: scan crosses each box's bottom edge
  const pending = ann.targets.filter((t) => !t.kf.length);
  const live = ann.targets.filter((t) => t.kf.length).map((t) => { const b = boxAt(t, scanStart)!; return { t, ft: scanStart + ((b.y + b.h + 30) / (H + 60)) * scanDur }; })
    .sort((a, b) => a.ft - b.ft);
  let prev = -99; for (const r of live) { r.ft = Math.max(r.ft, prev + 3); prev = r.ft; }
  const fired = live.filter((r) => local >= r.ft).length + (pending.length ? Math.min(pending.length, Math.max(0, Math.floor((local - scanStart) / 4))) : 0);
  const N = ann.targets.length;
  const done = local >= (live.length ? live[live.length - 1].ft : scanStart + 4 * pending.length) + 8;
  const out = 1 - seg(local, outAt, outAt + 6);
  const scanP = seg(local, scanStart, scanStart + scanDur);
  const lineY = lerp(-30, H + 30, scanP);
  const lineO = showLine ? seg(local, scanStart, scanStart + 3) * (1 - seg(local, scanStart + scanDur - 3, scanStart + scanDur)) : 0;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {lineO > 0 && (
        <>
          <div style={{ position: "absolute", left: 0, top: lineY - 60, width: W, height: 60, background: "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.10) 100%)", opacity: lineO }} />
          <div style={{ position: "absolute", left: 0, top: lineY - 1, width: W, height: 2, background: "rgba(255,255,255,0.85)", boxShadow: "0 0 14px rgba(255,255,255,0.7)", opacity: lineO }} />
        </>
      )}
      {live.map((r, i) => {
        if (local < r.ft) return null;
        const b = boxAt(r.t, local)!;
        const a = seg(local, r.ft, r.ft + 6, E_OUT);
        const s = lerp(1.75, 1, backLite(seg(local, r.ft, r.ft + 7)));
        const flash = 0.07 * seg(local, r.ft + 1, r.ft + 3) * (1 - seg(local, r.ft + 3, r.ft + 7));
        const la = seg(local, r.ft + 2, r.ft + 8, E_OUT);
        const above = b.y > 120;
        const lw = 64 + r.t.label.length * 23 + (r.t.sub ? 10 + r.t.sub.length * 9.5 : 0);   // approx label width (keeps it on screen)
        const lx = Math.min(Math.max(b.x - 8, 40), W - 40 - lw);
        const ly = above ? b.y - 66 : b.y + 14;   // no room above → label tucks inside the top of the box
        return (
          <React.Fragment key={r.t.id}>
            <Corners x={b.x} y={b.y} w={b.w} h={b.h} s={s} o={Math.min(1, a * 1.6) * 0.95} flash={flash} />
            <div style={{ position: "absolute", left: lx, top: ly, opacity: la, transform: `translateY(${lerp(above ? 6 : -6, 0, la)}px)`, display: "flex", alignItems: "center", gap: 10, padding: "6px 12px 7px", borderRadius: 8, background: "rgba(20,18,16,0.58)", backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)", whiteSpace: "nowrap" }}>
              <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 20, color: "#ECCE70" }}>{String(i + 1).padStart(2, "0")}</span>
              <span style={{ fontFamily: SANS, fontWeight: 700, fontSize: 22, color: "#FFFFFF" }}>{r.t.label}</span>
              {r.t.sub ? <span style={{ fontFamily: NUM, fontWeight: 600, fontStyle: "italic", fontSize: 14, letterSpacing: 1.5, color: "#C9CED6" }}>{r.t.sub}</span> : null}
            </div>
          </React.Fragment>
        );
      })}
      {pending.length > 0 && (
        <div style={{ position: "absolute", left: 96, top: 640, display: "flex", flexDirection: "column", gap: 10 }}>
          {pending.map((t, i) => {
            const la = seg(local, scanStart + 4 * i, scanStart + 4 * i + 7, E_OUT);
            return (
              <div key={t.id} style={{ opacity: la, transform: `translateX(${lerp(-14, 0, la)}px)`, display: "flex", gap: 10, alignItems: "baseline", color: "#EFECE6", fontFamily: SANS }}>
                <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 20, color: "#ECCE70" }}>{String(i + 1).padStart(2, "0")}</span>
                <span style={{ fontWeight: 700, fontSize: 22 }}>{t.label}</span>
                <span style={{ fontFamily: NUM, fontStyle: "italic", fontSize: 14, letterSpacing: 1.5, opacity: 0.7 }}>{t.sub}</span>
              </div>
            );
          })}
        </div>
      )}
      <div style={{ position: "absolute", right: 60, top: 54, fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 22, letterSpacing: 3, color: done ? "#ECCE70" : "#FFFFFF", textShadow: "0 1px 6px rgba(0,0,0,0.5)", opacity: seg(local, scanStart - 2, scanStart + 3) }}>
        {done ? "ANALYSIS · COMPLETE" : `SCAN ${String(Math.min(fired, N)).padStart(2, "0")}/${String(N).padStart(2, "0")}`}
      </div>
    </AbsoluteFill>
  );
};
