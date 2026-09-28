import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { StyleTokens } from "../styles/types";
import { isVideo, src } from "./util";

/** Full-frame photo / clip with the style grade and an optional slow push-in. */
export const Media: React.FC<{ file: string; st: StyleTokens; push?: boolean; dim?: number; origin?: string }> = ({ file, st, push, dim = 0, origin = "50% 50%" }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = push ? interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [1, st.pushScale], { extrapolateRight: "clamp" }) : 1.0;
  const style: React.CSSProperties = { width: "100%", height: "100%", objectFit: "cover", filter: st.grade };
  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: st.dark }}>
      <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: origin }}>
        {isVideo(file) ? <OffthreadVideo src={src(file)} muted style={style} /> : <Img src={src(file)} style={style} />}
      </AbsoluteFill>
      {dim > 0 ? <AbsoluteFill style={{ backgroundColor: `rgba(0,0,0,${dim})` }} /> : null}
    </AbsoluteFill>
  );
};
