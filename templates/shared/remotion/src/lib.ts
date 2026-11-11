import { Easing, interpolate } from "remotion";
export const W = 1440, H = 1080;
export const cl = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const seg = (f: number, a: number, b: number, e?: (x: number) => number) => (b <= a ? (f >= b ? 1 : 0) : interpolate(f, [a, b], [0, 1], { ...cl, easing: e }));
export const E_OUT = Easing.bezier(0.16, 1, 0.3, 1);
// v8 MOTION TEMPO (user 10-20: 一致的动效节奏): one timing scale for the whole film.
// enter/exit 8-10 f (E_OUT / spring), stagger 3-4 f, camera moves / route draws / 3D flights 16 f (E_IO), scene transitions 10 f.
export const TEMPO = { enter: 10, exit: 8, stagger: 4, move: 16, trans: 10 };
export const E_IO = Easing.bezier(0.65, 0, 0.35, 1);
export const OUT_CUBIC = Easing.out(Easing.cubic);
export const backLite = (p: number) => { const c = 0.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); }; // ~3% overshoot (house cap 4%)
export type Rect = { x: number; y: number; w: number; h: number };
export const lerpRect = (a: Rect, b: Rect, t: number): Rect => ({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), w: lerp(a.w, b.w, t), h: lerp(a.h, b.h, t) });
export const FULL: Rect = { x: 0, y: 0, w: W, h: H };
/** brand palette shared with the opener (map palette A / Canva) */
export { PAL } from "./palette";

// shared spring (overshoot ~19%, one small rebound) + squash pulse; settles in d frames (TEMPO.enter)
export const spring = (f: number, a: number, d = 10) => {
  const t = (f - a) / d;
  if (t <= 0) return { p: 0, o: 0, sq: 0 };
  if (t >= 1) return { p: 1, o: 1, sq: 0 };
  return { p: 1 - Math.exp(-5 * t) * Math.cos(9.5 * t), o: Math.min(1, t * 5), sq: Math.sin(Math.PI * Math.min(1, Math.max(0, (t - 0.15) / 0.45))) * (1 - t) };
};

