import EP from "../episode/episode.json";
// Persistent data-source footer (user: keep for the whole film, order 链家/德佑/富房/CENTURY 21; 富房 with its 不动产 box).
// Data: src/episode/brands.json; logos are alpha masks tinted with the scene ink (Mono).
import React from "react";
import { AbsoluteFill, interpolateColors } from "remotion";
import BRANDS from "../episode/brands.json";
import { Mono } from "./opener/Opener";
import { SANS } from "../fonts";

/** dark = 0 → paper wash + ink (map / opener), 1 → dark wash + white (presenter / B-roll) */
export const BrandStrip: React.FC<{ dark: number }> = ({ dark }) => {
  const ink = interpolateColors(dark, [0, 1], ["#483C32", "#F4F2EE"]);
  const sub = interpolateColors(dark, [0, 1], ["#8A7F74", "rgba(244,242,238,0.78)"]);
  const rule = interpolateColors(dark, [0, 1], ["rgba(138,127,116,0.33)", "rgba(255,255,255,0.3)"]);
  const wl = (a: number) => `rgba(239,236,230,${a * (1 - dark)})`;
  const wd = (a: number) => `rgba(14,13,12,${a * dark})`;
  return (
    <>
      <AbsoluteFill style={{ background: `linear-gradient(0deg, ${wl(1)} 0%, ${wl(0.93)} 70px, ${wl(0)} 150px)` }} />
      <AbsoluteFill style={{ background: `linear-gradient(0deg, ${wd(0.62)} 0%, ${wd(0.4)} 70px, ${wd(0)} 140px)` }} />
      <div style={{ position: "absolute", left: 60, right: 60, bottom: 38, height: 30, display: "flex", alignItems: "center", fontFamily: SANS }}>
        <Mono file={BRANDS.sourceMark.file} ar={BRANDS.sourceMark.ar} h={26} color={sub} />
        <div style={{ marginLeft: 12, fontSize: 15, fontWeight: 600, color: sub, letterSpacing: 1, whiteSpace: "nowrap" }}>{BRANDS.sourceMark.label}</div>
        <div style={{ width: 1, height: 22, background: rule, margin: "0 24px" }} />
        <div style={{ fontSize: 13, fontWeight: 500, color: sub, letterSpacing: 1, marginRight: 22, whiteSpace: "nowrap" }}>{BRANDS.rowLabel}</div>
        {BRANDS.row.map((b) => (
          <div key={b.name} style={{ marginRight: 30, opacity: 0.5 + 0.25 * dark }}><Mono file={b.file} ar={b.ar} h={b.h} color={ink} /></div>
        ))}
        {(EP as any).onScreenNotes !== false && <div style={{ marginLeft: "auto", fontSize: 13, fontWeight: 500, color: sub, letterSpacing: 1, whiteSpace: "nowrap" }}>房源卡片为示例数据 · 非实时房源</div>}
      </div>
    </>
  );
};
