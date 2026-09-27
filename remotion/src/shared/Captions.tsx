import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT_FAMILY, TEXT } from "./theme";

/** Full-length subtitles for the current narration segment. */
export const Captions: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const portrait = height > width;
  const opacity = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute",
        left: "8%",
        right: "8%",
        bottom: height * (portrait ? 0.2 : 0.1),
        display: "flex",
        justifyContent: "center",
        opacity,
      }}
    >
      <div
        style={{
          fontFamily: FONT_FAMILY,
          fontSize: width * (portrait ? 0.045 : 0.03),
          fontWeight: 700,
          color: TEXT,
          textAlign: "center",
          lineHeight: 1.35,
          padding: "0.25em 0.7em",
          background: "rgba(0,0,0,0.55)",
          borderRadius: 10,
          textShadow: "0 2px 6px rgba(0,0,0,0.6)",
        }}
      >
        {text}
      </div>
    </div>
  );
};
