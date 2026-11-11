// scanline-annotate-focus for footage (shotcraft references/shots/effects/scanline-annotate-focus.md), driven by per-clip JSON.
//  - a light scan line sweeps top→bottom at constant speed (zero easing); a target fires when the line crosses its box BOTTOM
//    (ft = start + (bottom+30)/(H+60)·dur), min 3 f apart, sorted by y
//  - corner viewfinder 1.08→1 over 8 f, focus flash ≤0.07, label 2 f after the box (box settles, then it is named)
//  - status line counts fired targets live: SCAN 0n/0N → ANALYSIS · COMPLETE
//  - after firing, boxes FOLLOW the tracked keyframes (annotations/<ID>.json from pipeline/track_annotations.py)
// Annotation JSON: { space: "video"|"image"|"frame", size?: [w,h], targets: [{ id, label, sub, kf: [[t_sec, x, y, w, h], ...] }] }  (x,y,w,h normalised 0–1)
import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, staticFile } from "remotion";
import { NUM, SANS } from "./fonts";
import { H, lerp, seg, W, E_OUT, type Rect } from "./lib";
import { sampleTracking } from "./annotationMotion";
import { BakedAnnotationChip, annotationChipSize } from "./bakedLabel";
import { overlapsRect } from "./leaderRouting";

export type Footage = { kind: "video" | "image" | "pending"; src?: string; still?: string; cx?: number; w?: number; h?: number; fps?: number; dur?: number; status: string; purpose?: string; label?: string; kb?: { s0: number; s1: number; ox0: number; oy0: number; ox1: number; oy1: number } };
export type Target = { id: string; label: string; sub?: string; kf: number[][]; t0?: number; t1?: number };   // t0/t1 (clip s, optional): fire no earlier than t0, fade out at t1 (montage clips)
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

/** the clip picture itself (video, Ken Burns still, or a labelled pending card) */
export const ClipMedia: React.FC<{ fo: Footage; id: string; local: number; inFrame?: number; grade?: string; transparent?: boolean; sceneRole?: "world" | "foreground" }> = ({ fo, id, local, inFrame = 12, grade, transparent, sceneRole = "foreground" }) => {
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
    <AbsoluteFill data-harmony-world={sceneRole === "world" ? fo.kind : undefined} data-world-source={sceneRole === "world" ? fo.src : undefined} style={{ overflow: "hidden", background: transparent ? undefined : "#111" }}>
      <AbsoluteFill style={{ transform: `scale(${g.s})`, transformOrigin: `${g.Ox}px ${g.Oy}px` }}>
        {fo.kind === "image" ? <Img src={staticFile(fo.src!)} style={{ ...style, objectFit: "cover" }} />
          : <OffthreadVideo src={staticFile(fo.src!)} muted transparent={transparent} startFrom={inFrame} style={{ ...style, objectFit: "cover" }} />}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Corners: React.FC<{ x: number; y: number; w: number; h: number; s: number; o: number; flash: number }> = ({ x, y, w, h, s, o, flash }) => {
  const arm = Math.max(12, Math.min(26, Math.min(w, h) / 3.2)), pad = 8;
  const x0 = x - pad, y0 = y - pad, x1 = x + w + pad, y1 = y + h + pad;
  const paths = [
    "M" + x0 + " " + (y0 + arm) + "L" + x0 + " " + y0 + "L" + (x0 + arm) + " " + y0,
    "M" + (x1 - arm) + " " + y0 + "L" + x1 + " " + y0 + "L" + x1 + " " + (y0 + arm),
    "M" + x0 + " " + (y1 - arm) + "L" + x0 + " " + y1 + "L" + (x0 + arm) + " " + y1,
    "M" + (x1 - arm) + " " + y1 + "L" + x1 + " " + y1 + "L" + x1 + " " + (y1 - arm),
  ];
  const cx = x + w / 2, cy = y + h / 2;
  return <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0, opacity: o, pointerEvents: "none", filter: "drop-shadow(0 1px 3px rgba(0,0,0,0.45))" }}>
    <g transform={"translate(" + cx + " " + cy + ") scale(" + s + ") translate(" + (-cx) + " " + (-cy) + ")"}>
      {paths.map((d, i) => <path key={i} d={d} fill="none" stroke="#FBFBF8" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />)}
      <rect x={x} y={y} width={w} height={h} fill="#FBFBF8" opacity={flash} />
    </g>
  </svg>;
};

/** overlay: scan line + tracked viewfinders + labels + status counter. local = frames since the clip is on screen. */
// mediaOffset = frames the clip has already been playing when the overlay's local 0 starts (overlay starts after the open move)
export const ScanAnnotate: React.FC<{ fo: Footage; ann?: Ann; local: number; inFrame?: number; mediaOffset?: number; scanStart?: number; scanDur?: number; showLine?: boolean; outAt?: number; reserved?: Rect[] }> = ({ fo, ann, local, inFrame = 12, mediaOffset = 0, scanStart = 5, scanDur = 24, showLine = true, outAt = 1e9, reserved = [] }) => {
  if (!ann || !ann.targets.length) return null;
  const sourceGeom = mediaGeom(fo, local + mediaOffset);
  // <OffthreadVideo startFrom> counts composition frames and plays in real time, so clip time = (inFrame + frames played) / 30
  // regardless of the source fps (Muse clips are 24 fps); keyframes are in clip seconds.
  const tSec = (fr: number) => (fo.kind === "video" ? (inFrame + mediaOffset + fr) / FPS : (mediaOffset + fr) / FPS);
  const boxAt = (t: Target, fr: number) => {
    const b = sampleTracking(t.kf, tSec(fr), ann.space === "frame" ? W : sourceGeom.dw, ann.space === "frame" ? H : sourceGeom.dh);
    if (!b) return null;
    if (ann.space === "frame") return { x: b[0] * W, y: b[1] * H, w: b[2] * W, h: b[3] * H };
    const g = mediaGeom(fo, fr + mediaOffset);
    const [x0, y0] = g.map(b[0], b[1]), [x1, y1] = g.map(b[0] + b[2], b[1] + b[3]);
    return { x: Math.max(0, x0), y: Math.max(0, y0), w: Math.min(W, x1) - Math.max(0, x0), h: Math.min(H, y1) - Math.max(0, y0) };
  };
  // trigger frames: scan crosses each box's bottom edge
  const pending = ann.targets.filter((t) => !t.kf.length);
  const frAt = (sec: number) => sec * FPS - (fo.kind === "video" ? inFrame : 0) - mediaOffset;   // clip seconds -> local frame
  const live = ann.targets.filter((t) => t.kf.length).map((t) => { const b = boxAt(t, scanStart)!; const sf = scanStart + ((b.y + b.h + 30) / (H + 60)) * scanDur; return { t, ft: t.t0 !== undefined ? Math.max(sf, frAt(t.t0)) : sf }; })
    .sort((a, b) => a.ft - b.ft);
  let prev = -99; for (const r of live) { r.ft = Math.max(r.ft, prev + 3); prev = r.ft; }
  const protectedAreas: Rect[] = [
    { x: 0, y: 0, w: W, h: 172 }, { x: 0, y: H - 216, w: W, h: 216 }, ...reserved,
  ];
  const clampLabel = (box: Rect) => ({ ...box, x: Math.min(Math.max(box.x, 40), W - 40 - box.w), y: Math.min(Math.max(box.y, 176), H - 224 - box.h) });
  const placeLabel = (b: Rect, w: number, h: number, choice: number) => {
    const options = [
      { x: b.x - 8, y: b.y - h - 16 }, { x: b.x + b.w - w + 8, y: b.y - h - 16 },
      { x: b.x - 8, y: b.y + b.h + 16 }, { x: b.x + b.w - w + 8, y: b.y + b.h + 16 },
      { x: b.x - w - 16, y: b.y + (b.h - h) / 2 }, { x: b.x + b.w + 16, y: b.y + (b.h - h) / 2 },
    ];
    return clampLabel({ ...options[choice], w, h });
  };
  // Keep one placement side for the target's entire visible interval, rather than
  // choosing a new side every frame as a box crosses a threshold.
  const labelChoices = new Map<string, number>();
  const labelSizes = new Map<string, { w: number; h: number }>();
  for (const r of live) {
    const size = annotationChipSize(r.t.label, r.t.sub);
    labelSizes.set(r.t.id, size);
    const last = r.t.t1 !== undefined ? frAt(r.t.t1) : Math.max(r.ft + 1, (fo.dur ?? 7) * FPS - inFrame - mediaOffset);
    let best = 0, bestCost = Infinity;
    for (let choice = 0; choice < 6; choice++) {
      let cost = choice * 2;
      for (let j = 0; j <= 4; j++) {
        const frame = lerp(r.ft + 8, last, j / 4);
        const box = boxAt(r.t, frame);
        if (!box) continue;
        const candidate = placeLabel(box, size.w, size.h, choice);
        cost += protectedAreas.filter((p) => overlapsRect(candidate, p, 8)).length * 10000;
        for (const prev of live) {
          const previous = labelChoices.get(prev.t.id);
          if (previous === undefined) continue;
          const pbox = boxAt(prev.t, frame), psz = labelSizes.get(prev.t.id)!;
          if (pbox && overlapsRect(candidate, placeLabel(pbox, psz.w, psz.h, previous), 10)) cost += 10000;
        }
      }
      if (cost < bestCost) { bestCost = cost; best = choice; }
    }
    labelChoices.set(r.t.id, best);
  }
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
        const tOut = r.t.t1 !== undefined ? 1 - seg(local, frAt(r.t.t1), frAt(r.t.t1) + 5) : 1;
        if (tOut <= 0) return null;
        const b = boxAt(r.t, local)!;
        const a = seg(local, r.ft, r.ft + 6, E_OUT);
        const s = lerp(1.08, 1, seg(local, r.ft, r.ft + 8, E_OUT));
        const flash = 0.07 * seg(local, r.ft + 1, r.ft + 3) * (1 - seg(local, r.ft + 3, r.ft + 7));
        const la = seg(local, r.ft + 2, r.ft + 8, E_OUT);
        const size = labelSizes.get(r.t.id)!;
        const label = placeLabel(b, size.w, size.h, labelChoices.get(r.t.id)!);
        if (b.w < 2 || b.h < 2) return null;
        return (
          <div key={r.t.id} style={{ opacity: tOut }}>
            <Corners x={b.x} y={b.y} w={b.w} h={b.h} s={s} o={Math.min(1, a * 1.6) * 0.95} flash={flash} />
            <div style={{ position: "absolute", left: 0, top: 0, opacity: la, transform: "translate3d(" + label.x + "px," + label.y + "px,0)" }}>
              <div style={{ transform: "translate3d(0," + lerp(6, 0, la) + "px,0)" }}>
                <BakedAnnotationChip index={i + 1} label={r.t.label} sub={r.t.sub} />
              </div>
            </div>
          </div>
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
      {/* status line: back near its original spot (right 60, top 54 -> 66), just below the one-row SocialBadge (ends ~y 50) */}
      <div style={{ position: "absolute", right: 60, top: 66, fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 22, letterSpacing: 3, color: done ? "#ECCE70" : "#FFFFFF", textShadow: "0 1px 6px rgba(0,0,0,0.5)", opacity: seg(local, scanStart - 2, scanStart + 3) }}>
        {done ? "ANALYSIS · COMPLETE" : `SCAN ${String(Math.min(fired, N)).padStart(2, "0")}/${String(N).padStart(2, "0")}`}
      </div>
    </AbsoluteFill>
  );
};

