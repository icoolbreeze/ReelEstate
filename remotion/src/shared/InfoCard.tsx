import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { Card } from "../types";
import { FONT_FAMILY, MUTED } from "./theme";
import { lerp, popIn, riseIn, seg, E } from "./motion";

/**
 * Designed info card in the video-shotcraft "progressive assemble" style:
 * body rises into place, accent header settles, then each bullet's dot pops
 * while its text rises in — staggered like fields being captured. A very slow
 * push keeps the card alive during the read-through hold.
 */
export const InfoCard: React.FC<{ card: Card; accent: string; side: "left" | "right" | "center" }> = ({
  card,
  accent,
  side,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const portrait = height > width;
  const lines = card.lines ?? [];

  const w = portrait ? width * 0.86 : width * 0.4;
  const pos: React.CSSProperties =
    side === "center" || portrait
      ? { left: (width - w) / 2, top: height * (portrait ? 0.13 : 0.11) }
      : side === "left"
        ? { left: width * 0.05, top: height * 0.11 }
        : { right: width * 0.05, top: height * 0.11 };

  const push = seg(frame, 0, 90, E.outQuad); // slow scale 1→1.03 across 3s
  const radius = width * (portrait ? 0.026 : 0.016);

  return (
    <div
      style={{
        position: "absolute",
        width: w,
        ...pos,
        transform: `scale(${lerp(push, 1, 1.03)})`,
        transformOrigin: side === "left" ? "bottom left" : "bottom right",
      }}
    >
      <div
        style={{
          background: "#FFFFFF",
          borderRadius: radius,
          boxShadow:
            "0 2px 6px rgba(31,45,80,0.06), 0 24px 60px rgba(31,45,80,0.18)",
          border: "1px solid rgba(31,45,80,0.06)",
          overflow: "hidden",
          fontFamily: FONT_FAMILY,
          ...riseIn(frame, 0, 26, 14),
        }}
      >
        {/* Accent header band */}
        <div
          style={{
            position: "relative",
            padding: `${height * 0.022}px ${width * 0.026}px`,
            background: `linear-gradient(120deg, ${accent}14, ${accent}05)`,
            ...riseIn(frame, 4, 16, 12),
          }}
        >
          <div
            style={{
              width: width * 0.032,
              height: width * 0.006,
              borderRadius: 99,
              background: accent,
              marginBottom: height * 0.012,
            }}
          />
          <div
            style={{
              fontSize: width * (portrait ? 0.052 : 0.03),
              fontWeight: 800,
              letterSpacing: 0.5,
              color: "#1B2330",
              lineHeight: 1.25,
            }}
          >
            {card.title}
          </div>
        </div>

        {/* Bullet rows */}
        {lines.length > 0 ? (
          <div style={{ padding: `${height * 0.014}px ${width * 0.026}px ${height * 0.026}px` }}>
            {lines.map((line, i) => {
              const f0 = 12 + i * 5;
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: width * 0.014,
                    padding: `${height * 0.01}px 0`,
                  }}
                >
                  <span
                    style={{
                      flex: "0 0 auto",
                      width: width * 0.012,
                      height: width * 0.012,
                      borderRadius: "50%",
                      background: accent,
                      marginTop: width * (portrait ? 0.014 : 0.008),
                      boxShadow: `0 0 0 4px ${accent}1F`,
                      ...popIn(frame, f0, 10),
                    }}
                  />
                  <span
                    style={{
                      fontSize: width * (portrait ? 0.038 : 0.0205),
                      lineHeight: 1.5,
                      color: "#333C4B",
                      ...riseIn(frame, f0, 12, 10),
                    }}
                  >
                    {line}
                  </span>
                </div>
              );
            })}
          </div>
        ) : null}

        {/* Footer hint */}
        <div
          style={{
            padding: `${height * 0.012}px ${width * 0.026}px`,
            borderTop: "1px solid rgba(31,45,80,0.07)",
            fontSize: width * (portrait ? 0.024 : 0.012),
            color: MUTED,
            ...riseIn(frame, 14 + lines.length * 5, 12, 10),
          }}
        >
          信息仅供参考，以实际看房与合同约定为准
        </div>
      </div>
    </div>
  );
};
