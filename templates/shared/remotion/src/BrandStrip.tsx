
// Persistent data-source footer (user: keep for the whole film, order 链家/德佑/富房/CENTURY 21; 富房 with its 不动产 box).
// Data: src/episode/brands.json; logos are alpha masks tinted with the scene ink (Mono).
import React from "react";
import { AbsoluteFill, interpolateColors, staticFile } from "remotion";
import { SANS } from "./fonts";
const Mono: React.FC<{ file: string; ar: number; h: number; color: string }> = ({ file, ar, h, color }) => {
  const u = `url(${staticFile(file)})`;
  return <div style={{ width: h * ar, height: h, background: color, WebkitMaskImage: u, maskImage: u, WebkitMaskSize: "100% 100%", maskSize: "100% 100%", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat" }} />;
};





/** dark = 0 → paper wash + ink (map / opener), 1 → dark wash + white (presenter / B-roll) */
export const ListingBrandStrip: React.FC<BrandProps> = ({ dark = 0, brands: BRANDS, episode: EP }) => {
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
        {(EP as any).onScreenNotes !== false && (EP as any).sampleData === true && <div style={{ marginLeft: "auto", fontSize: 13, fontWeight: 500, color: sub, letterSpacing: 1, whiteSpace: "nowrap" }}>房源卡片为示例数据 · 非实时房源</div>}
      </div>
    </>
  );
};


type Brand = { name: string; file: string; ar: number; h: number };
type BrandData = { sourceMark: { file: string; ar: number; label: string }; rowLabel?: string; row: Brand[] };
type BrandProps = { dark?: number; brands: BrandData; episode: { onScreenNotes?: boolean; sampleData?: boolean } };
export const KnowledgeBrandStrip: React.FC<BrandProps> = ({ brands: BRANDS, episode: EP }) => {
  const ink = "#334155";
  const sub = "#64748B";
  return (
    <>
      <AbsoluteFill style={{
        background: "linear-gradient(0deg, rgba(255,255,255,0.94) 0%, rgba(255,255,255,0.65) 48px, rgba(255,255,255,0) 110px)",
        pointerEvents: "none"
      }} />
      <div style={{ position: "absolute", left: 64, right: 64, bottom: 28, height: 34, display: "flex", alignItems: "center", fontFamily: SANS }}>
        <Mono file={BRANDS.sourceMark.file} ar={BRANDS.sourceMark.ar} h={24} color={ink} />
        <div style={{ marginLeft: 10, fontSize: 15, fontWeight: 700, color: ink, letterSpacing: 0.5, whiteSpace: "nowrap" }}>{BRANDS.sourceMark.label}</div>
        <div style={{ width: 1, height: 18, background: "rgba(15, 23, 42, 0.12)", margin: "0 20px" }} />
        {BRANDS.row.map((b) => (
          <div key={b.name} style={{ marginRight: 24, opacity: 0.8 }}><Mono file={b.file} ar={b.ar} h={b.h} color={ink} /></div>
        ))}
        {(EP as any).onScreenNotes !== false && (
          <div style={{ marginLeft: "auto", fontSize: 13, fontWeight: 600, color: sub, letterSpacing: 0.5, whiteSpace: "nowrap" }}>知识科普 · 数据以官方来源为准</div>
        )}
      </div>
    </>
  );
};

