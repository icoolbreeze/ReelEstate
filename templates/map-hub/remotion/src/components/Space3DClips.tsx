// L13+L14 "basic-3d-scene" (v8): port of video-shotcraft demos/camera/basic-3d-scene/Basic3DScene.tsx (Apache-2.0,
// shot credited to remotion-bits.dev). Kept from the source: impress-style stations with their own pose, camera = pose inverse
// (scale(1/s) rotateZ(-rz) rotateY(-ry) rotateX(-rx) translate3d(-x,-y,-z)), chained flights with the asymmetric
// bezier(0.62,0,0.16,1), 30 % hop pull-back mid-flight, 1.5 % creep during holds, focus by station distance
// (opacity 0.22-1 + blur 0-7 px), world-space 3D motes for parallax, closing pulled-back OVERVIEW where every card lights up.
// Changed: chapter posters -> real footage cards (one clip plays per station, people blurred upstream), stations are timed
// from narration anchors {line, t}; per-station focus zoom + scanline + tracked corner box on the subject; light warm episode palette (off-white stage, white-bordered
// cards, purple/yellow tags, boxes and scanline, warm dust) instead of graphite; temporal-sampling motion blur dropped (would decode every video up to 8x per frame).
import React from "react";
import { AbsoluteFill, Easing, OffthreadVideo, Sequence, interpolate, staticFile } from "remotion";
import { sampleTracking } from "../annotationMotion";
import { BakedAnnotationChip } from "../bakedLabel";

type Pose = { x: number; y: number; z: number; rx: number; ry: number; rz: number; s: number };
type Station = { id: string; src: string; label: string; sub: string; kf: number[][]; arrive: number; pose: Pose };
export type Space3DSpec = { f0: number; f1: number; fly: number; stations: Station[]; overview: { arrive: number; pose: Pose } };

const FPS = 30, CW = 1040, CH = 780, PERSP = 2600;
const cl = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const FLY = Easing.bezier(0.62, 0, 0.16, 1), OUT = Easing.bezier(0.16, 1, 0.3, 1), SMOOTH = Easing.bezier(0.65, 0, 0.35, 1);
const ramp = (f: number, a: number, d: number, e = SMOOTH) => interpolate(f, [a, a + Math.max(1, d)], [0, 1], { ...cl, easing: e });
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const hash = (n: number) => { const x = Math.sin(n * 91.345 + 47.853) * 43758.5453; return x - Math.floor(x); };
const camT = (c: Pose) => `scale(${(1 / c.s).toFixed(5)}) rotateZ(${(-c.rz).toFixed(4)}deg) rotateY(${(-c.ry).toFixed(4)}deg) rotateX(${(-c.rx).toFixed(4)}deg) translate3d(${(-c.x).toFixed(3)}px,${(-c.y).toFixed(3)}px,${(-c.z).toFixed(3)}px)`;
const poseT = (p: Pose) => `translate3d(${p.x}px,${p.y}px,${p.z}px) rotateX(${p.rx}deg) rotateY(${p.ry}deg) rotateZ(${p.rz}deg) scale(${p.s})`;
const MOTES = Array.from({ length: 50 }, (_, i) => ({ x: -2600 + hash(i * 3.1) * 13000, y: -2200 + hash(i * 5.7 + 1) * 4400, z: -3200 + hash(i * 7.3 + 2) * 3600, r: 3 + hash(i * 11.9 + 3) * 7, a: 0.25 + hash(i * 13.1 + 4) * 0.5 }));

export const Space3DClips: React.FC<{ spec: Space3DSpec; f: number }> = ({ spec, f }) => {
  const { f0, f1, fly, stations: S, overview: OV } = spec;
  if (f < f0 - 2 || f > f1 + 12) return null;
  const poses = [...S.map((s) => s.pose), OV.pose], arrive = [...S.map((s) => s.arrive), OV.arrive];
  // camera: chained flights into each station (flight ends on the station's arrive frame)
  const cam: Pose = { ...poses[0] }; cam.s = mix(1.06, 1, ramp(f, f0, 30));
  let af = 0, hop = 0;
  for (let i = 1; i < poses.length; i++) {
    const u = ramp(f, arrive[i] - fly, fly, FLY); af += u;
    (Object.keys(cam) as (keyof Pose)[]).forEach((k) => { cam[k] = mix(cam[k], poses[i][k], u); });
    if (i < poses.length - 1 && u > 0 && u < 1) hop = 0.3 * Math.sin(Math.PI * u);
  }
  cam.s *= 1 + hop;
  let creep = 0;
  for (let i = 0; i < S.length; i++) { const nx = arrive[i + 1] - fly; creep += ramp(f, arrive[i] + 4, Math.max(8, nx - arrive[i] - 4)) * (1 - ramp(f, nx, 14)); }
  cam.s *= 1 - 0.015 * creep;
  cam.s *= 1 - 0.015 * ramp(f, OV.arrive + 4, 30);
  const over = ramp(f, OV.arrive - fly, fly);
  const sceneO = Math.min(ramp(f, f0 - 2, 10, OUT), 1 - ramp(f, f1, 10, OUT));
  return (
    <AbsoluteFill style={{ opacity: sceneO, background: "radial-gradient(ellipse 95% 75% at 50% 20%, #FBFAF7 0%, #F3F0EA 55%, #E6E0D6 100%)" }}>
      <AbsoluteFill style={{ overflow: "hidden", perspective: `${PERSP}px` }}>
        <div style={{ position: "absolute", left: "50%", top: "46%", width: 0, height: 0, transformStyle: "preserve-3d", transform: camT(cam) }}>
          {MOTES.map((m, k) => <div key={k} style={{ position: "absolute", left: -m.r, top: -m.r, width: m.r * 2, height: m.r * 2, borderRadius: "50%", transform: `translate3d(${m.x}px,${m.y}px,${m.z}px)`, background: `radial-gradient(circle, rgba(196,150,82,${(m.a * 0.45).toFixed(3)}) 0%, rgba(196,150,82,0) 70%)` }} />)}
          {S.map((st, i) => {
            const d = Math.min(1, Math.abs(af - i));
            const focus = Math.max(1 - d, over * 0.92);
            const lift = (1 - d) * 18;
            const playFrom = arrive[i] - fly - 6;                                // clip starts as the camera leaves for it
            const here = af > i - 0.02 && af < i + 0.02;                       // camera parked on this station
            const parkA = arrive[i], parkB = arrive[i + 1] - fly;
            const zk = here ? ramp(f, parkA + 2, 14, OUT) * (1 - ramp(f, parkB - 6, 8)) : 0;
            const t = (f - playFrom) / FPS, b = sampleTracking(st.kf, t, CW, CH);
            const cx = b ? b[0] + b[2] / 2 : 0.5, cy = b ? b[1] + b[3] / 2 : 0.5, zoom = 1 + 0.16 * zk;
            const ox = (0.5 - cx) * CW * (zoom - 1), oy = (0.5 - cy) * CH * (zoom - 1);
            const bx = b ? (b[0] - 0.5) * CW * zoom + CW / 2 + ox : 0, by = b ? (b[1] - 0.5) * CH * zoom + CH / 2 + oy : 0;
            const x0 = Math.max(10, bx), y0 = Math.max(10, by), x1 = Math.min(CW - 10, bx + (b ? b[2] * CW * zoom : 0)), y1 = Math.min(CH - 10, by + (b ? b[3] * CH * zoom : 0));
            const scanP = ramp(f, parkA - 2, 16), scanO = here ? ramp(f, parkA - 2, 3) * (1 - ramp(f, parkA + 11, 3)) : 0;
            const boxO = here ? ramp(f, parkA + 6, 6, OUT) * (1 - ramp(f, parkB - 4, 6)) : 0;
            const tagO = Math.max(focus > 0.6 ? 1 : 0, over);
            return (
              <div key={st.id} style={{ position: "absolute", left: -CW / 2, top: -CH / 2, width: CW, height: CH, transform: `${poseT(st.pose)} translateZ(${lift.toFixed(2)}px)`, opacity: 0.22 + 0.78 * focus, filter: focus < 0.985 ? `blur(${((1 - focus) * 7).toFixed(2)}px)` : undefined }}>
                <div style={{ position: "absolute", inset: -14, borderRadius: 18, background: "#FFFFFF", boxShadow: "0 22px 50px rgba(72,60,50,0.22), 0 5px 14px rgba(72,60,50,0.14)" }} />
                <div style={{ position: "absolute", inset: 0, borderRadius: 12, overflow: "hidden", background: "#EFECE6" }}>
                  <Sequence from={playFrom} layout="none">
                    <OffthreadVideo src={staticFile(st.src)} muted style={{ position: "absolute", width: CW, height: CH, objectFit: "cover", transform: `translate(${ox}px, ${oy}px) scale(${zoom})` }} />
                  </Sequence>
                  {scanO > 0 && <><div style={{ position: "absolute", left: 0, top: mix(-30, CH + 30, scanP) - 60, width: CW, height: 60, background: "linear-gradient(180deg, rgba(123,47,247,0) 0%, rgba(123,47,247,0.16) 100%)", opacity: scanO }} />
                    <div style={{ position: "absolute", left: 0, top: mix(-30, CH + 30, scanP) - 1, width: CW, height: 2, background: "#7B2FF7", boxShadow: "0 0 10px rgba(123,47,247,0.55)", opacity: scanO }} /></>}
                  {boxO > 0 && b && x1 - x0 > 30 && y1 - y0 > 30 && (
                    <svg width={CW} height={CH} style={{ position: "absolute", left: 0, top: 0, opacity: boxO }}>
                      <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke="#7B2FF7" strokeWidth={3} strokeDasharray="12 9" />
                      {[[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]].map(([px, py, sx, sy], k) => <path key={k} d={`M${px} ${py + sy * 30} L${px} ${py} L${px + sx * 30} ${py}`} fill="none" stroke="#FFE600" strokeWidth={7} strokeLinecap="round" />)}
                    </svg>
                  )}
                </div>
                <div style={{ position: "absolute", left: 22, top: 22, opacity: tagO }}>
                  <BakedAnnotationChip index={i + 1} label={st.label} sub={st.sub} variant="station" />
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
