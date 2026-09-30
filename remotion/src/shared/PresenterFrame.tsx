import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { PresenterMode } from "../types";

type Props = {
  mode: PresenterMode;
  clip?: string; // relative to public dir (= project dir)
  clipStart?: number; // seconds
  accent: string;
};

/**
 * The creator's talking-head footage. fullscreen fills the frame; pip-left / pip-right
 * is a small rounded window in the bottom corner (above InfoBar / captions).
 * Without a clip there is nothing to show — callers render Backdrop instead.
 */
export const PresenterFrame: React.FC<Props> = ({ mode, clip, clipStart = 0, accent }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;
  const enter = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 12 });

  if (!clip) return null;

  const body = (
    <OffthreadVideo
      src={staticFile(clip)}
      trimBefore={Math.round(clipStart * fps)}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
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
