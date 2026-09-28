import React from "react";
import type { InfoField } from "../shared/InfoBar";
import type { StyleTokens } from "../styles/types";
import { W } from "./util";

/** Always-on compliance strip (公约必填：类型/面积/位置/价格+有效期/机构) + global badges, at the top edge. */
export const ComplianceStrip: React.FC<{ fields: InfoField[]; badges: string[]; st: StyleTokens }> = ({ fields, badges, st }) => (
  <div style={{ position: "absolute", left: 0, top: 0, width: W, height: 40, background: st.stripBg, display: "flex", alignItems: "center", gap: 10, padding: "0 18px", boxSizing: "border-box" }}>
    {badges.map((b) => (
      <span key={b} style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 17, color: "#fff", background: "rgba(200,30,40,.85)", borderRadius: 4, padding: "1px 8px", whiteSpace: "nowrap" }}>
        {b}
      </span>
    ))}
    <span style={{ flex: 1, textAlign: "right", fontFamily: st.fonts.sans, fontWeight: 500, fontSize: 18, color: st.stripText, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
      {fields.filter((x) => x.value).map((x) => x.value).join("｜")}
    </span>
  </div>
);

/** “素材来源” tag, top-left, on any outside footage (map, stock, AI clips). */
export const SourceTag: React.FC<{ text: string; st: StyleTokens }> = ({ text, st }) => (
  <div style={{ position: "absolute", left: 24, top: 54, fontFamily: st.fonts.sans, fontWeight: 500, fontSize: 18, color: "rgba(255,255,255,.9)", background: "rgba(0,0,0,.38)", padding: "3px 10px", borderRadius: 4 }}>
    {text}
  </div>
);

/** Per-shot disclosure badge (AI生成 / 效果图 / 户型示意 …), top-right under the strip. */
export const ShotBadge: React.FC<{ labels: string[]; st: StyleTokens }> = ({ labels, st }) =>
  labels.length ? (
    <div style={{ position: "absolute", right: 24, top: 54, display: "flex", gap: 8 }}>
      {labels.map((l) => (
        <span key={l} style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 20, color: "#fff", background: "rgba(200,30,40,.85)", padding: "3px 10px", borderRadius: 4 }}>
          {l}
        </span>
      ))}
    </div>
  ) : null;

export const OutroCTA: React.FC<{ cta: string; agency: string; st: StyleTokens; frame: number }> = ({ cta, agency, st, frame }) => {
  const k = Math.min(1, Math.max(0, (frame - 8) / st.enterFrames));
  return (
    <div style={{ position: "absolute", left: 0, width: W, top: 660, display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
      <div style={{ opacity: k, transform: `scale(${0.9 + 0.1 * k})`, background: st.accent, color: "#111", fontFamily: st.fonts.sans, fontWeight: 900, fontSize: 58, padding: "14px 40px", borderRadius: 60, boxShadow: "0 12px 30px rgba(0,0,0,.3)" }}>{cta}</div>
      <div style={{ opacity: k, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 28, color: "#fff", textShadow: "0 2px 8px rgba(0,0,0,.6)" }}>{agency}</div>
    </div>
  );
};
