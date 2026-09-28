// Transition-in effects played over the first frames of a shot. Motion grammar after video-shotcraft
// cards wipe-transitions (clock-wipe) and color-block-step-wipe (Apache-2.0). Re-skinned to StyleTokens.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import type { TransitionProps } from "./types";
import { clamp01, ease, prog } from "./kit";

const W = 1440;
const H = 1080;
const CX = W / 2;
const CY = H / 2;
const R = 1100;

/** clock-wipe: a radar hand sweeps 360° linearly from 12 o'clock; the new shot opens inside the sweep; bright edge fades out. */
export const ClockWipe: React.FC<TransitionProps> = ({ st, duration }) => {
  const f = useCurrentFrame();
  const len = Math.min(duration, 22);
  const theta = 360 * clamp01(f / len);
  if (f >= len + 4) return null;
  // cover = the part NOT yet swept (from theta to 360)
  const pts: string[] = [`${CX}px ${CY}px`];
  const N = 60;
  for (let i = 0; i <= N; i++) {
    const a = ((theta + ((360 - theta) * i) / N) * Math.PI) / 180;
    pts.push(`${(CX + R * Math.sin(a)).toFixed(1)}px ${(CY - R * Math.cos(a)).toFixed(1)}px`);
  }
  const a = (theta * Math.PI) / 180;
  const x2 = CX + R * Math.sin(a);
  const y2 = CY - R * Math.cos(a);
  const edge = 1 - prog(f, len, len + 4);
  return (
    <AbsoluteFill>
      {theta < 360 ? <AbsoluteFill style={{ background: st.dark, clipPath: `polygon(${pts.join(", ")})` }} /> : null}
      <svg width={W} height={H} style={{ position: "absolute", inset: 0, opacity: edge }}>
        <line x1={CX} y1={CY} x2={x2} y2={y2} stroke={st.accent} strokeWidth={14} strokeOpacity={0.35} strokeLinecap="round" />
        <line x1={CX} y1={CY} x2={x2} y2={y2} stroke={st.accent} strokeWidth={4} strokeLinecap="round" />
      </svg>
    </AbsoluteFill>
  );
};

/** color-block-step-wipe: an accent block covers the frame, then retreats in 3 hard discrete steps (no easing between steps). */
export const ColorBlockWipe: React.FC<TransitionProps> = ({ st }) => {
  const f = useCurrentFrame();
  const steps = [1, 0.66, 0.33, 0];
  const i = Math.min(steps.length - 1, Math.floor(f / 4));
  const cover = steps[i];
  if (cover <= 0) return null;
  const barK = ease.outCubic(clamp01(f / 3));
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 0, top: 0, width: W * cover, height: H, background: st.accent }} />
      <div style={{ position: "absolute", left: W * cover - 18 * barK, top: 0, width: 18, height: H, background: st.dark, opacity: cover < 1 ? 1 : 0 }} />
    </AbsoluteFill>
  );
};
