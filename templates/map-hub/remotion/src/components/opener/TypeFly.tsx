// shotcraft assemble-then-type-flyin, adapted to 1440×1080 (@贝壳-TV v3).
// Reference: /workspace/video-shotcraft/references/shots/effects/assemble-then-type-flyin.md
//   + demos/effects/assemble-then-type-flyin/AssembleThenTypeFlyin.tsx (design stage 480×270, ×3 here).
// Phase 1 "shell": wordless pieces (pill/card backgrounds, braces, rules, icons, logo) fly in flat
//   (translate + ≤8° rotate) with a back-ease capped at ~3% overshoot (house rule ≤4%), motion blur cleared at a>0.97.
// Phase 2 "type": every character flies in from 3D space with its own seeded dx/dy/dz + rotateX/Y/Z,
//   perspective written per character, outCubic landing, transform set to 'none' once landed.
import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";

const S = 3; // shotcraft design px -> our px (480 -> 1440)
const cl = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const seg = (f: number, a: number, b: number, e?: (x: number) => number) => interpolate(f, [a, b], [0, 1], { ...cl, easing: e });
const lerp = (t: number, a: number, b: number) => a + (b - a) * t;
const outCubic = Easing.out(Easing.cubic);
export const rand = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
// ~3% overshoot back-ease (outBack with c1=0.9 instead of 1.70158 → the reference's ~10% is over our 4% cap)
export const backLite = (p: number) => { const c = 0.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); };

export const SHELL_DUR = 12;   // frames (reference 0.14×156≈22f; overshoot peak→rest ≈5f, within the 8f settle cap)
export const CHAR_DUR = 16;    // frames (reference 0.13×156≈20f)

/** Phase-1 style for a wordless piece. from = start offset px, rot = start rotation deg, ft = takeoff frame. */
export const shellStyle = (f: number, from: [number, number], rot: number, ft: number): React.CSSProperties => {
  const p = seg(f, ft, ft + SHELL_DUR);
  const a = backLite(p);
  const sp = p > 0 && a < 0.97 ? 1 - a : 0;
  return {
    opacity: f >= ft ? Math.min(1, seg(f, ft, ft + 5) * 1.5) : 0,
    transform: p >= 1 ? undefined : `translate(${lerp(a, from[0], 0)}px,${lerp(a, from[1], 0)}px) rotate(${lerp(a, rot, 0)}deg)`,
    filter: sp > 0.03 ? `blur(${Math.min(4, sp * 2 * 2)}px)` : undefined,
  };
};

export type Run = { s?: string; node?: React.ReactNode; style?: React.CSSProperties };
/** Phase-2 text block: chars in normal inline flow (no absolute per-char layout), only transforms animate.
 *  runs with `node` fly as one glyph (used for the live distance counter). step = frames between characters. */
export const FlyText: React.FC<{ runs: Run[]; start: number; step: number; seed: number; style?: React.CSSProperties; amp?: number }> = ({ runs, start, step, seed, style, amp = 1 }) => {
  const f = useCurrentFrame();
  let ci = 0;
  return (
    <span style={{ whiteSpace: "nowrap", ...style }}>
      {runs.map((r, ri) => {
        const glyphs: React.ReactNode[] = r.node !== undefined ? [r.node] : Array.from(r.s ?? "");
        return (
          <span key={ri} style={r.style}>
            {glyphs.map((g, k) => {
              const idx = ci++;
              const kk = seed + idx;
              const ft = start + idx * step;
              const a = seg(f, ft, ft + CHAR_DUR, outCubic);
              const c = {
                dx: (rand(kk) - 0.5) * 340 * S * amp, dy: (rand(kk + 50) - 0.5) * 260 * S * amp, dz: (-120 - rand(kk + 99) * 300) * S * amp,
                rx: (rand(kk + 7) - 0.5) * 340, ry: (rand(kk + 13) - 0.5) * 380, rz: (rand(kk + 23) - 0.5) * 240,
              };
              return (
                <span key={k} style={{
                  display: "inline-block",
                  opacity: a > 0 ? Math.min(1, a * 1.8) : 0,
                  transform: a >= 1 ? "none" :
                    `perspective(${600 * S}px) translate3d(${lerp(a, c.dx, 0)}px,${lerp(a, c.dy, 0)}px,${lerp(a, c.dz, 0)}px) ` +
                    `rotateX(${lerp(a, c.rx, 0)}deg) rotateY(${lerp(a, c.ry, 0)}deg) rotateZ(${lerp(a, c.rz, 0)}deg)`,
                }}>{g === " " ? "\u00a0" : g}</span>
              );
            })}
          </span>
        );
      })}
    </span>
  );
};
/** frame at which the last glyph of a block has landed */
export const landsAt = (start: number, n: number, step: number) => start + (n - 1) * step + CHAR_DUR;
