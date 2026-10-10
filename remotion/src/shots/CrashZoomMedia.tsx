import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import { isVideo, src } from "./util";

// shotcraft crash-zoom-punch: a six-frame hard landing from the hook cut.
// Overshoot is forbidden beyond 4% (rules/motion.md), so the image brakes
// onto scale 1 with no elastic kick; motion blur sells the impact.
const PUNCH_FRAMES = 6;
const START_SCALE = 1.45;

export const CrashZoomMedia: React.FC<{ file: string; st: StyleTokens; duration: number }> = ({ file, st, duration }) => {
  const frame = useCurrentFrame();

  const punch = interpolate(frame, [0, PUNCH_FRAMES], [START_SCALE, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const blur = interpolate(frame, [0, PUNCH_FRAMES - 1], [14, 0], { extrapolateRight: "clamp" });
  // video-taste §7.4: keep drifting after the punch so the hold never freezes.
  const drift = 1 + 0.025 * (Math.max(0, frame - PUNCH_FRAMES) / Math.max(1, duration - PUNCH_FRAMES));
  const scale = frame < PUNCH_FRAMES ? punch : drift;

  const style: React.CSSProperties = { width: "100%", height: "100%", objectFit: "cover", filter: st.grade };
  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: st.dark }}>
      <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: "50% 42%", filter: blur > 0.2 ? `blur(${blur}px)` : undefined }}>
        {isVideo(file) ? <OffthreadVideo src={src(file)} muted style={style} /> : <Img src={src(file)} style={style} />}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
