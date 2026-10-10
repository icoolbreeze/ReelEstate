import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

/**
 * Bottom brand bar. Renders <Img> logos from staticFile paths only — it never
 * draws wordmarks or text substitutes. When brandLogos is empty it renders
 * nothing (no real logo files for 链家 / 德佑 / 富房 / CENTURY 21 / 中环 exist
 * in this repo, so default props use []).
 */
export const BrandBar: React.FC<{ brandLogos: string[] }> = ({ brandLogos }) => {
  if (brandLogos.length === 0) return null;
  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 56,
          alignItems: "center",
          marginBottom: 22,
        }}
      >
        {brandLogos.map((logo) => (
          <Img
            key={logo}
            src={staticFile(logo)}
            style={{ height: 46, width: "auto", objectFit: "contain" }}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};
