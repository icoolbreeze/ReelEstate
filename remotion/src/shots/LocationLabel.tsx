import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { LocationInfo } from "../types";
import { E, pop, seg, W } from "./util";

/**
 * “{ 无影棚 }” location label (MediaStorm C-type). Heavy sans ≈165 px glyphs, braces ≈212 px, centred at y≈570.
 * f0 braces appear ~200 px apart and open over 12 frames (ease-out, ~70% in the first 4 frames);
 * characters pop one by one from the middle (110%→100%); red dot #D60F28 at f4; settled by f14-19 (0.5-0.65 s).
 * On 4:3 long labels auto-shrink (the report suggests 110-130 px). The `sub` line carries the distance basis —
 * distance / time claims need a verifiable source (rules/compliance: no “X分钟” wording).
 */
export const LocationLabel: React.FC<{ loc: LocationInfo; st: StyleTokens; cy?: number }> = ({ loc, st, cy = 560 }) => {
  const f = useCurrentFrame();
  const chars = [...loc.main];
  const n = chars.length;
  // CJK ≈0.95em wide, ASCII/digits ≈0.55em — size so total ≤1080 px.
  const units = chars.reduce((a, c) => a + (/[\u4e00-\u9fff]/.test(c) ? 1 : 0.55), 0);
  const size = Math.min(165, Math.floor(1000 / Math.max(1, units)));
  const braceSize = Math.min(212, size * 1.28);
  const textW = chars.reduce((a, c) => a + (/[\u4e00-\u9fff]/.test(c) ? size : size * 0.55), 0);
  const open = E.outExpo(seg(f, 0, 12));
  const halfFinal = textW / 2 + braceSize * 0.42;
  const half = 100 + (halfFinal - 100) * open;
  const mid = (n - 1) / 2;
  const order = chars.map((_, i) => Math.abs(i - mid)).map((d) => Math.round(d));
  const dot = pop(f, 4, 5);
  const subK = seg(f, 14, 20);
  const braceStyle: React.CSSProperties = {
    position: "absolute",
    top: cy - braceSize * 0.62,
    fontFamily: st.fonts.latin,
    fontWeight: 300,
    fontSize: braceSize,
    lineHeight: 1,
    color: st.text,
    textShadow: "0 4px 18px rgba(0,0,0,.35)",
  };
  const scrimK = seg(f, 0, 10);
  return (
    <div style={{ position: "absolute", left: 0, top: 0, width: W, height: 1080 }}>
      <div
        style={{
          position: "absolute",
          left: W / 2 - 620,
          top: cy - size * 0.95,
          width: 1240,
          height: size * 1.9,
          borderRadius: size,
          background: "radial-gradient(closest-side, rgba(10,12,16,.26), rgba(10,12,16,0))",
          opacity: scrimK,
        }}
      />
      <div style={{ ...braceStyle, left: W / 2 - half - braceSize * 0.3 }}>{"{"}</div>
      <div style={{ ...braceStyle, left: W / 2 + half - braceSize * 0.18 }}>{"}"}</div>
      <div style={{ position: "absolute", left: (W - textW) / 2, top: cy - size * 0.56, width: textW, display: "flex" }}>
        {chars.map((c, i) => {
          const p = pop(f, 4 + order[i] * 2, 5);
          const s = p.k <= 0 ? 0 : 1 + 0.1 * Math.sin(Math.PI * p.k) * (1 - p.k) + (p.scale - 1) * 0.3;
          return (
            <span
              key={i}
              style={{
                width: /[\u4e00-\u9fff]/.test(c) ? size : size * 0.55,
                textAlign: "center",
                fontFamily: st.fonts.heavy,
                fontWeight: 900,
                fontSize: size,
                lineHeight: 1.1,
                color: st.text,
                display: "inline-block",
                transform: `scale(${s})`,
                opacity: p.k > 0 ? 1 : 0,
                textShadow: st.hardShadow ?? "0 4px 18px rgba(0,0,0,.35)",
              }}
            >
              {c}
            </span>
          );
        })}
        <div
          style={{
            position: "absolute",
            right: -size * 0.28,
            top: -size * 0.06,
            width: 45,
            height: 45,
            borderRadius: 23,
            background: st.name === "mediastorm" ? "#D60F28" : st.red,
            transform: `scale(${dot.scale})`,
          }}
        />
      </div>
      {loc.sub ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            width: W,
            top: cy + braceSize * 0.5,
            textAlign: "center",
            fontFamily: st.fonts.sans,
            fontWeight: 500,
            fontSize: 30,
            color: "rgba(255,255,255,.88)",
            opacity: subK,
            textShadow: "0 2px 8px rgba(0,0,0,.5)",
          }}
        >
          {loc.sub}
        </div>
      ) : null}
    </div>
  );
};
