import React from "react";
import { useVideoConfig } from "remotion";
import { FONT_FAMILY } from "./theme";

/**
 * Placeholder corner badges: 示例数据 / 含AI合成配音 / 广告 / 效果图.
 * NOTE: platform-level AI labels must still be ticked when publishing (see rules/workflow.md).
 */
export const DisclaimerBadge: React.FC<{ labels: string[] }> = ({ labels }) => {
  const { width } = useVideoConfig();
  if (labels.length === 0) return null;
  return (
    <div style={{ position: "absolute", top: width * 0.02, right: width * 0.02, display: "flex", gap: 8 }}>
      {labels.map((l) => (
        <span
          key={l}
          style={{
            fontFamily: FONT_FAMILY,
            fontSize: width * (width < 1200 ? 0.022 : 0.013),
            color: "#fff",
            background: "rgba(0,0,0,0.55)",
            border: "1px solid rgba(255,255,255,0.5)",
            borderRadius: 6,
            padding: "2px 10px",
          }}
        >
          {l}
        </span>
      ))}
    </div>
  );
};
