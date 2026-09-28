import React from "react";
import { AbsoluteFill, OffthreadVideo, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { ShotPresenter } from "../types";
import { src, W } from "./util";

/**
 * Talking head. `startFrom` = global frame of the shot so the clip plays continuously across cuts.
 * fullscreen fills the frame; pip-left / pip-right is a corner window kept inside the platform safe area.
 * mediastorm: hard cut (no entrance); qiuzhi: spring pop, circular window with ring.
 */
export const StylePresenter: React.FC<{ clip: string; mode: ShotPresenter; st: StyleTokens; startFrom: number }> = ({ clip, mode, st, startFrom }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (mode === "none") return null;
  const video = <OffthreadVideo src={src(clip)} muted trimBefore={Math.max(0, startFrom)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: st.grade }} />;
  if (mode === "fullscreen") return <AbsoluteFill>{video}</AbsoluteFill>;
  const p = st.pip;
  const k = st.motion === "spring" ? spring({ frame: f, fps, config: { damping: 14, stiffness: 170, mass: 0.7 } }) : 1;
  const left = mode === "pip-left" ? p.margin : W - p.margin - p.w;
  return (
    <div
      style={{
        position: "absolute",
        left,
        top: 1080 - p.bottom - p.h,
        width: p.w,
        height: p.h,
        borderRadius: p.radius,
        overflow: "hidden",
        boxShadow: `0 0 0 4px ${p.ring}, 0 14px 36px rgba(0,0,0,.35)`,
        transform: `scale(${k})`,
        transformOrigin: mode === "pip-left" ? "bottom left" : "bottom right",
        background: "#000",
      }}
    >
      {video}
    </div>
  );
};
