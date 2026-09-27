import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { PresenterMode } from "../types";
import { FONT_FAMILY, MUTED } from "./theme";

type Props = {
  mode: PresenterMode;
  clip?: string; // relative to public dir (= project dir)
  clipStart?: number; // seconds
  accent: string;
};

/**
 * The creator's talking-head footage. fullscreen fills the frame; pip-left / pip-right
 * is a small rounded window in the bottom corner (above InfoBar / captions).
 */
export const PresenterFrame: React.FC<Props> = ({ mode, clip, clipStart = 0, accent }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;
  const enter = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 12 });

  const body = clip ? (
    <OffthreadVideo
      src={staticFile(clip)}
      trimBefore={Math.round(clipStart * fps)}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  ) : (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 50% 38%, #3a4252 0%, #1b2029 70%)`,
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT_FAMILY,
        color: MUTED,
      }}
    >
      <div style={{ width: "22%", aspectRatio: "1", borderRadius: "50%", background: "#4a5366" }} />
      <div style={{ width: "40%", height: "22%", marginTop: "2%", borderRadius: "40% 40% 0 0", background: "#4a5366" }} />
      <div style={{ position: "absolute", top: "6%", fontSize: mode === "fullscreen" ? width * 0.018 : width * 0.012 }}>
        主播画面占位（raw/ 口播素材）
      </div>
    </AbsoluteFill>
  );

  if (mode === "fullscreen") {
    return <AbsoluteFill style={{ opacity: interpolate(enter, [0, 1], [0.6, 1]) }}>{body}</AbsoluteFill>;
  }

  const w = width * (portrait ? 0.3 : 0.26);
  const h = w * (4 / 3) * (portrait ? 1 : 0.75); // 4:3-ish landscape box, 3:4 box on portrait
  const margin = width * 0.025;
  const bottom = height * (portrait ? 0.31 : 0.17);
  return (
    <div
      style={{
        position: "absolute",
        width: w,
        height: h,
        bottom,
        [mode === "pip-left" ? "left" : "right"]: margin,
        borderRadius: width * 0.012,
        overflow: "hidden",
        border: `3px solid ${accent}`,
        boxShadow: "0 12px 36px rgba(0,0,0,0.45)",
        transform: `scale(${interpolate(enter, [0, 1], [0.85, 1])})`,
        transformOrigin: mode === "pip-left" ? "bottom left" : "bottom right",
        opacity: enter,
      }}
    >
      {body}
    </div>
  );
};
