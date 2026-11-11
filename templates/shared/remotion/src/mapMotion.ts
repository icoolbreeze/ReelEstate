// Shared map camera math for the opener and the hub.
// One projection, one trajectory. Every value is a function of the inputs only.

export const TY = 60;
export const END_S = 1.72;
export type Cam = { s: number; fx: number; fy: number; tilt: number; P: number };

/** Mirrors HubPlane / MapPlane CSS: origin (fx,fy), then translate3d + rotateX + scale, perspective P. */
export const projectPoint = (c: Cam, x: number, y: number) => {
  const th = (c.tilt * Math.PI) / 180;
  const dx = (x - c.fx) * c.s;
  const dy = (y - c.fy) * c.s;
  const X = 720 + dx;
  const Y = 540 + TY + dy * Math.cos(th);
  const Z = dy * Math.sin(th);
  const k = c.P / (c.P - Z);
  return { x: 720 + (X - 720) * k, y: 540 + (Y - 540) * k, k };
};

/** Screen scale that follows the lens. 1 at the opener's settled scale. Does not change layout width. */
export const cardLensScale = (s: number) => s / END_S;

export const overlayTransform = (x: number, y: number) => `translate3d(${x}px, ${y}px, 0)`;

export type CamKnot = { f: number; cam: Cam };
export type CamSeg = { f0: number; f1: number; next: number; a: Cam; b: Cam };

const PUSH_RAMP = 8;
const PUSH_S = 0.03;
const PUSH_FX = 5;

/** Quintic smoothstep. Value and first derivative are 0 at 0 and 1 at 1. */
export const smoother = (u: number) => {
  const t = Math.min(1, Math.max(0, u));
  return t * t * t * (t * (t * 6 - 15) + 10);
};

export const mixCam = (a: Cam, b: Cam, p: number): Cam => ({
  s: a.s * Math.pow(b.s / a.s, p),
  fx: a.fx + (b.fx - a.fx) * p,
  fy: a.fy + (b.fy - a.fy) * p,
  tilt: a.tilt + (b.tilt - a.tilt) * p,
  P: a.P + (b.P - a.P) * p,
});

/** Map-move length from the gap until the next knot starts. Not TEMPO.move. */
export const moveDuration = (gap: number) => {
  if (gap >= 48) return 36;
  if (gap >= 28) return 24;
  return Math.max(12, gap - 4);
};

const integSmoother = (x: number) => {
  const u = Math.min(1, Math.max(0, x));
  return u * u * u * u * (u * (u - 3) + 2.5);
};

/** Frames of full-speed push accumulated over a hold of length T, t frames after arrival. */
export const pushIntegral = (t: number, T: number) => {
  if (T < PUSH_RAMP * 2 || t <= 0) return 0;
  const tt = Math.min(t, T);
  const up = Math.min(tt, PUSH_RAMP);
  let acc = PUSH_RAMP * integSmoother(up / PUSH_RAMP);
  if (tt > PUSH_RAMP) acc += Math.max(0, Math.min(tt, T - PUSH_RAMP) - PUSH_RAMP);
  // A last segment has no following knot (T is infinite). It keeps the plateau
  // through the end card. A finite hold eases the push out before the next move.
  if (Number.isFinite(T) && tt > T - PUSH_RAMP) {
    const v1 = (T - tt) / PUSH_RAMP;
    acc += PUSH_RAMP * (integSmoother(1) - integSmoother(v1));
  }
  return acc;
};

export const applyPush = (cam: Cam, framesOfPush: number): Cam => {
  const sec = framesOfPush / 30;
  return { ...cam, s: cam.s * (1 + PUSH_S * sec), fx: cam.fx + PUSH_FX * sec };
};

/**
 * Move starts closer than 8 frames collapse into one destination.
 * A start within 8 frames of the home pose begins at the home frame;
 * the pose ON the home frame stays `home.cam` (the ease has not moved yet).
 */
export const mergeMoveStarts = (homeF: number, moves: CamKnot[]): CamKnot[] => {
  const sorted = [...moves].sort((a, b) => a.f - b.f);
  const out: CamKnot[] = [];
  for (const k of sorted) {
    if (!out.length && k.f - homeF < 8) {
      out.push({ f: homeF, cam: k.cam });
      continue;
    }
    const prev = out[out.length - 1];
    if (prev && k.f - prev.f < 8) out[out.length - 1] = { f: prev.f, cam: k.cam };
    else out.push(k);
  }
  return out;
};

export const buildTrack = (home: CamKnot, moves: CamKnot[]): CamSeg[] => {
  const segs: CamSeg[] = [];
  let pose = home.cam;
  for (let i = 0; i < moves.length; i++) {
    const start = Math.max(moves[i].f, home.f);
    const nextStart = i + 1 < moves.length ? moves[i + 1].f : Number.POSITIVE_INFINITY;
    const gap = nextStart === Number.POSITIVE_INFINITY ? 80 : nextStart - start;
    let dur = moveDuration(gap);
    if (nextStart !== Number.POSITIVE_INFINITY) dur = Math.min(dur, Math.max(12, nextStart - start - 4));
    const f1 = start + dur;
    const dest = moves[i].cam;
    segs.push({ f0: start, f1, next: nextStart, a: pose, b: dest });
    const holdLen = nextStart === Number.POSITIVE_INFINITY ? 0 : Math.max(0, nextStart - f1);
    pose = applyPush(dest, pushIntegral(holdLen, holdLen));
  }
  return segs;
};

export const evalTrack = (home: CamKnot, segs: CamSeg[], f: number): Cam => {
  if (f <= home.f || segs.length === 0) return home.cam;
  let i = 0;
  for (let k = 0; k < segs.length; k++) if (segs[k].f0 <= f) i = k;
  const s = segs[i];
  if (f < s.f0) return home.cam;
  if (f < s.f1) return mixCam(s.a, s.b, smoother((f - s.f0) / (s.f1 - s.f0)));
  const T = s.next === Number.POSITIVE_INFINITY ? Number.POSITIVE_INFINITY : s.next - s.f1;
  return applyPush(s.b, pushIntegral(f - s.f1, T));
};

/** True when a near-stop of 3 frames is followed by a step over 2px. */
export const velocityGlitch = (steps: number[]) => {
  let stall = 0;
  for (const step of steps) {
    if (step < 0.15) stall += 1;
    else {
      if (stall >= 3 && step > 2) return true;
      stall = 0;
    }
  }
  return false;
};

