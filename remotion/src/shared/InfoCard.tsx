import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Card } from "../types";
import { FONT_FAMILY, PANEL, TEXT } from "./theme";

/** Simple animated info card (placeholder for Canva-designed cards in canva/). */
export const InfoCard: React.FC<{ card: Card; accent: string; side: "left" | "right" | "center" }> = ({ card, accent, side }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const portrait = height > width;
  const s = spring({ frame, fps, config: { damping: 18, stiffness: 120 } });
  const w = portrait ? width * 0.84 : width * 0.44;
  const pos: React.CSSProperties =
    side === "center" || portrait
      ? { left: (width - w) / 2, top: height * (portrait ? 0.14 : 0.12) }
      : side === "left"
        ? { left: width * 0.05, top: height * 0.12 }
        : { right: width * 0.05, top: height * 0.12 };
  return (
    <div
      style={{
        position: "absolute",
        width: w,
        ...pos,
        background: PANEL,
        borderRadius: 18,
        borderLeft: `8px solid ${accent}`,
        padding: `${height * 0.03}px ${width * 0.03}px`,
        fontFamily: FONT_FAMILY,
        color: TEXT,
        transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)`,
        opacity: s,
        boxShadow: "0 18px 50px rgba(0,0,0,0.35)",
      }}
    >
      <div style={{ fontSize: width * (portrait ? 0.055 : 0.032), fontWeight: 800, color: accent, marginBottom: height * 0.015 }}>
        {card.title}
      </div>
      {(card.lines ?? []).map((line, i) => {
        const o = interpolate(frame, [6 + i * 5, 14 + i * 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ fontSize: width * (portrait ? 0.04 : 0.022), lineHeight: 1.6, opacity: o }}>
            · {line}
          </div>
        );
      })}
    </div>
  );
};
