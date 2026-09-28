import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { SpecInfo } from "../types";
import { seg, typed } from "./util";

/**
 * Spec card (MediaStorm A-type “X-OCN LT”): left margin 76 px; Latin title cap height ≈95 px (Montserrat SemiBold);
 * Chinese lines glyph ≈34 px (40 px font) on a 59 px pitch, 30 px below the title; white + soft white glow, no plate.
 * Title fades in over 8 frames while the whole card drifts right; lines type in from +18 frames at ~1 char/frame.
 */
export const SpecCard: React.FC<{ spec: SpecInfo; st: StyleTokens; top?: number }> = ({ spec, st, top = 250 }) => {
  const f = useCurrentFrame();
  const k = seg(f, 0, st.enterFrames);
  const drift = f * 1.4;
  const titleSize = 110;
  const warn = spec.variant === "warning";
  return (
    <div style={{ position: "absolute", left: 76 + drift, top, width: 1200 }}>
      <div
        style={{
          fontFamily: st.fonts.latin,
          fontWeight: 600,
          fontSize: titleSize,
          lineHeight: 1,
          color: st.text,
          opacity: k,
          letterSpacing: 1,
          textShadow: st.hardShadow ?? st.textGlow,
          whiteSpace: "nowrap",
          display: "flex",
          alignItems: "center",
          gap: 22,
        }}
      >
        <span style={{ width: 18, height: titleSize * 0.72, background: st.accent, display: "inline-block", opacity: warn ? 1 : 0.85 }} />
        {spec.title}
      </div>
      <div style={{ marginTop: 30 }}>
        {spec.lines.map((line, i) => {
          const start = 18 + i * 8;
          const t = typed(line, f, start, 1);
          return (
            <div
              key={i}
              style={{
                height: 59,
                fontFamily: st.fonts.sans,
                fontWeight: 500,
                fontSize: 40,
                lineHeight: "59px",
                color: st.text,
                textShadow: st.textGlow,
                whiteSpace: "nowrap",
              }}
            >
              {t}
            </div>
          );
        })}
      </div>
    </div>
  );
};
