import React from "react";
import { useVideoConfig } from "remotion";
import { FONT_FAMILY, PANEL, TEXT } from "./theme";

export type InfoField = { label: string; value: string };

/**
 * Always-on bar with the fields mandated by 视频号《房地产行业公约》(2026-05-12):
 * 房产类型 / 面积口径 / 街道或小区 / 真实价格+有效期 / 中介机构全称 (+ 期房: 开发商, 预售证号).
 */
export const InfoBar: React.FC<{ fields: InfoField[]; accent: string }> = ({ fields, accent }) => {
  const { width, height } = useVideoConfig();
  const portrait = height > width;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: portrait ? height * 0.05 : 0,
        padding: `${height * 0.012}px ${width * 0.02}px`,
        background: PANEL,
        borderTop: `3px solid ${accent}`,
        display: "flex",
        flexWrap: "wrap",
        gap: `${height * 0.006}px ${width * 0.016}px`,
        fontFamily: FONT_FAMILY,
        fontSize: width * (portrait ? 0.024 : 0.0145),
        color: TEXT,
      }}
    >
      {fields
        .filter((f) => f.value)
        .map((f) => (
          <span key={f.label} style={{ whiteSpace: "nowrap" }}>
            <span style={{ color: accent, marginRight: 6 }}>{f.label}</span>
            {f.value}
          </span>
        ))}
    </div>
  );
};
