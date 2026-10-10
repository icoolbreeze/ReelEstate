import { Easing, interpolate } from "remotion";
export const W = 1440, H = 1080;
export const cl = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const seg = (f: number, a: number, b: number, e?: (x: number) => number) => (b <= a ? (f >= b ? 1 : 0) : interpolate(f, [a, b], [0, 1], { ...cl, easing: e }));
export const E_OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const E_IO = Easing.bezier(0.65, 0, 0.35, 1);
export const OUT_CUBIC = Easing.out(Easing.cubic);
export const backLite = (p: number) => { const c = 0.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); }; // ~3% overshoot (house cap 4%)
export type Rect = { x: number; y: number; w: number; h: number };
export const lerpRect = (a: Rect, b: Rect, t: number): Rect => ({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), w: lerp(a.w, b.w, t), h: lerp(a.h, b.h, t) });
export const FULL: Rect = { x: 0, y: 0, w: W, h: H };
/** brand palette shared with the opener (map palette A / Canva) */
export const PAL = { land: "#EFECE6", ink: "#483C32", sub: "#8A7F74", accent: "#9A463D", card: "#FBFAF7", gold: "#ECCE70", border: "rgba(31,28,23,0.07)", shadow: "0 8px 28px rgba(31,28,23,0.14)" };
