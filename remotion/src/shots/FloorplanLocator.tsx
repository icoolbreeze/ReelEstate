import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { FloorplanRoom } from "../types";
import { seg } from "./util";

/**
 * Bottom-left floor-plan locator (MediaStorm 600x230 @1920 → 450x170 @1440x1080, left 48, bottom 150).
 * White card with a line drawing; the current room is filled with the accent at 85%, black label 28 px.
 * Rooms are normalised rects (0-1). `schematic` adds a small “示意” tag (not to scale).
 */
export const FloorplanLocator: React.FC<{ rooms: FloorplanRoom[]; current?: string; st: StyleTokens; schematic?: boolean }> = ({ rooms, current, st, schematic }) => {
  const f = useCurrentFrame();
  const W = 450;
  const H = 170;
  const pad = 12;
  const iw = W - pad * 2;
  const ih = H - pad * 2;
  const cur = rooms.find((r) => r.key === current);
  const k = seg(f, 0, 4);
  return (
    <div style={{ position: "absolute", left: 48, bottom: 150, width: W, height: H, borderRadius: 8, background: "rgba(255,255,255,0.96)", boxShadow: "0 8px 24px rgba(0,0,0,.25)", opacity: k }}>
      <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0 }}>
        {rooms.map((r) => (
          <rect
            key={r.key}
            x={pad + r.x * iw}
            y={pad + r.y * ih}
            width={r.w * iw}
            height={r.h * ih}
            fill={r.key === current ? st.accent : "#FFFFFF"}
            fillOpacity={r.key === current ? 0.85 : 1}
            stroke="#1B1B1B"
            strokeWidth={2.5}
          />
        ))}
      </svg>
      {cur ? (
        <div
          style={{
            position: "absolute",
            left: pad + (cur.x + cur.w / 2) * iw,
            top: pad + (cur.y + cur.h / 2) * ih,
            transform: "translate(-50%, -50%)",
            background: "#111",
            color: "#fff",
            fontFamily: st.fonts.sans,
            fontWeight: 700,
            fontSize: 26,
            lineHeight: 1,
            padding: "5px 10px 6px",
            borderRadius: 4,
            whiteSpace: "nowrap",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span style={{ width: 12, height: 12, borderRadius: 6, background: "#E8471C", display: "inline-block" }} />
          {cur.zh}
        </div>
      ) : null}
      {schematic ? (
        <div style={{ position: "absolute", right: 8, top: 6, fontFamily: st.fonts.sans, fontSize: 15, color: "#666" }}>户型示意 · 非比例</div>
      ) : null}
    </div>
  );
};
