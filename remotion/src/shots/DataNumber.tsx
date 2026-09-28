import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { NumberInfo } from "../types";
import { seg, W } from "./util";

/** Big data number (MediaStorm B-type “45ms”): gold #ECCE70 + orange glow, digits ≈110 px tall; red when over the limit. */
export const DataNumber: React.FC<{ num: NumberInfo; st: StyleTokens; cy?: number }> = ({ num, st, cy = 560 }) => {
  const f = useCurrentFrame();
  const k = seg(f, 0, 6);
  const color = num.over ? st.red : st.gold;
  const glow = num.over ? "0 0 26px rgba(214,15,40,.6)" : "0 0 26px rgba(255,150,40,.55), 0 0 4px rgba(255,190,90,.6)";
  const capK = seg(f, 10, 10 + st.enterFrames);
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: cy - 120, display: "flex", flexDirection: "column", alignItems: "center" }}>
      {num.caption ? (
        <div style={{ fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 36, color: st.text, opacity: capK, textShadow: st.textGlow, marginBottom: 6 }}>{num.caption}</div>
      ) : null}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 18, opacity: k, transform: `scale(${0.92 + 0.08 * k})` }}>
        <div style={{ fontFamily: st.fonts.latin, fontWeight: 800, fontSize: 157, lineHeight: 1, color, textShadow: glow, letterSpacing: 2 }}>{num.value}</div>
        {num.unit ? <div style={{ fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 40, color: "rgba(235,235,235,.8)", paddingBottom: 14 }}>{num.unit}</div> : null}
      </div>
    </div>
  );
};
