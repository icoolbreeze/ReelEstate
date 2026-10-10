import { Easing, spring } from "remotion";

// ---------------------------------------------------------------------------
// Spring config shared by the title glyphs and the room cards.
//
// Measured limits (per docs/TASK-hook-matte.md): peak mapped scale <= 1.04
// (overshoot <= 4%) and settled within 8 frames (|scale - 1| < 0.005, held for
// every sample through +8 frames).
//
// Scale is mapped 0.6 -> 1:  scale = 0.6 + 0.4 * springValue.
// Sampling spring() for frames 0..60 with the starting config
// { damping: 18, stiffness: 180, mass: 0.8 } gave peak scale 1.0110 (pass)
// but did not settle until spring frame 13 (fail). Raising DAMPING ONLY, per
// the spec, to 19.5 gives (verified per-frame samples, see
// hook_matte/check_spring.mjs + hook_matte/spring.json):
//   frame  8: scale 0.99504  (|scale-1| = 0.00496 < 0.005)
//   frames 8..16 all stay inside the 0.005 band
//   peak scale 1.00499 @ frame 11 (<= 1.04)
//   measureSpring({fps:30, config}) = 15
// No overshootClamping is used.
// ---------------------------------------------------------------------------
export const TITLE_SPRING = {
  damping: 19.5,
  stiffness: 180,
  mass: 0.8,
} as const;

export const FPS = 30;
export const DURATION_FRAMES = 150;
export const CANVAS_W = 1440;
export const CANVAS_H = 1080;

// Slow camera push over frames 0..149: Easing.bezier(0.33, 0, 0.2, 1), no spring.
const pushEase = Easing.bezier(0.33, 0, 0.2, 1);

export const cameraProgress = (frame: number): number => {
  const x = Math.min(1, Math.max(0, frame / (DURATION_FRAMES - 1)));
  return pushEase(x);
};

/** Spring value for an element whose own flight starts at global frame `start`. */
export const flightSpring = (frame: number, start: number): number | null => {
  if (frame < start) return null;
  return spring({ frame: frame - start, fps: FPS, config: TITLE_SPRING });
};

/** scale 0.6 -> 1 mapping from a raw spring value. */
export const flyScale = (s: number): number => 0.6 + 0.4 * s;

/**
 * Translate that moves the element center from `fromCenter` to its settled
 * `settledCenter` as the spring value s goes 0 -> 1.
 */
export const flyTranslate = (
  s: number,
  fromCenter: { x: number; y: number },
  settledCenter: { x: number; y: number },
): { x: number; y: number } => ({
  x: (1 - s) * (fromCenter.x - settledCenter.x),
  y: (1 - s) * (fromCenter.y - settledCenter.y),
});
