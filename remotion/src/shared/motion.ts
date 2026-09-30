// Motion primitives adapted from video-shotcraft (Apache-2.0,
// https://github.com/Vincentwei1021/video-shotcraft), frame-driven instead of normalized-time.
// SPDX-License-Identifier: Apache-2.0
import type { CSSProperties } from "react";

export const E = {
  linear: (t: number) => t,
  outQuad: (t: number) => t * (2 - t),
  outCubic: (t: number) => 1 - Math.pow(1 - t, 3),
  outQuart: (t: number) => 1 - Math.pow(1 - t, 4),
  outExpo: (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  outBack: (t: number, s = 1.70158) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2),
};

export const lerp = (t: number, a: number, b: number) => a + (b - a) * t;

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// Progress 0→1 over the frame range [f0,f1], passed through an easing curve.
export const seg = (frame: number, f0: number, f1: number, ease: (x: number) => number = E.linear) =>
  ease(clamp01((frame - f0) / (f1 - f0)));

// rise: settle downward by `dy`px while fading in. pop: spring from scale 0.4 with a slight overshoot.
export const riseIn = (frame: number, f0: number, dy = 14, duration = 12): CSSProperties => {
  const k = seg(frame, f0, f0 + duration, E.outCubic);
  return { opacity: k, transform: `translateY(${lerp(k, dy, 0)}px)` };
};

export const popIn = (frame: number, f0: number, duration = 12): CSSProperties => {
  const k = seg(frame, f0, f0 + duration, E.outCubic);
  return { opacity: Math.min(1, k * 1.4), transform: `scale(${lerp(E.outBack(k), 0.4, 1)})` };
};
