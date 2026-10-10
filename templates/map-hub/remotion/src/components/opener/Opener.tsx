// @贝壳-TV listing opener v3 (v2 + assemble-then-type-flyin map text + 贝壳 data-source marks): archive-page multiplane (shotcraft MultiplaneReal layout logic) -> scanline-annotate-focus
// -> dolly zoom (card pinned, world swells, map perspective deepens) -> card morphs into an offset photo pin (one take).
// Data: src/data/listings.json (示例数据) + src/data/mapdata.json (Amap route / POIs in comp-plane px).
import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, interpolateColors, staticFile, useCurrentFrame } from "remotion";
import "../../fonts";
import { NUM, SANS, TITLE } from "../../fonts";
import DATA from "../../episode/listings.json";
import MAP from "../../episode/mapdata.json";
import BRANDS from "../../episode/brands.json";
import SAT from "../../episode/sat.json";
import { FlyText, shellStyle } from "./TypeFly";

export const DURATION = 240;

// ---------- themes (card world only; the map act is always dark) ----------
type Theme = { stage: string; card: string; border: string; text: string; sub: string; mute: string; hair: string; chip: string; shadow: string; shadowHero: string; bgO: number; bgFilter: string; scanCore: string; scanTint: string; corner: string; chosenBg: string; chosenInk: string };
const DARK: Theme = {
  stage: "#121315", card: "#1B1C20", border: "rgba(255,255,255,0.06)", text: "#F4F3EF", sub: "#A9ADB5", mute: "#6C7179", hair: "rgba(255,255,255,0.08)", chip: "rgba(255,255,255,0.16)",
  shadow: "0 10px 30px rgba(0,0,0,0.42)", shadowHero: "0 30px 80px rgba(0,0,0,0.6)", bgO: 0.55, bgFilter: "blur(2.5px) saturate(0.7) brightness(0.85)",
  scanCore: "rgba(251,251,248,0.92)", scanTint: "214,235,0", corner: "#B8BDC7", chosenBg: "#D6EB00", chosenInk: "#141214",
};
export const LIGHT: Theme = {
  stage: "#EFECE6", card: "#FBFAF7", border: "rgba(31,28,23,0.07)", text: "#1E1C19", sub: "#6F6A62", mute: "#A39D93", hair: "rgba(31,28,23,0.09)", chip: "rgba(31,28,23,0.16)",
  shadow: "0 8px 28px rgba(31,28,23,0.14)", shadowHero: "0 30px 80px rgba(31,28,23,0.30)", bgO: 0.5, bgFilter: "blur(3px) saturate(0.7)",
  scanCore: "rgba(30,28,25,0.85)", scanTint: "143,163,0", corner: "#3A3732", chosenBg: "#1E1C19", chosenInk: "#F4F3EF",
};
// map palettes (Canva): A = 玫瑰和尤加利叶 birth-spring + 桥上的风景 muted-overview; B = 洗衣房 here-at-home + 夜晚下的小路 dark-road-curve (+ 明月当空照 crack-of-dawn gold)
export type MapPal = { id: string; land: string; ink: string; sub: string; accent: string; card: string };
export const MAP_PALS: Record<string, MapPal> = {
  A: { id: "A", land: "#EFECE6", ink: "#483C32", sub: "#8A7F74", accent: "#9A463D", card: "#FBFAF7" },
  B: { id: "B", land: "#F1F0EB", ink: "#2F3338", sub: "#808080", accent: "#C98D26", card: "#FFFFF0" },
  // test only: palette A with the flova gpt-image-2.5 edited base (flova_edit/), not the default
  flovaA: { id: "flovaA", land: "#EFECE6", ink: "#483C32", sub: "#8A7F74", accent: "#9A463D", card: "#FBFAF7" },
  // Google satellite (WGS-84 imagery warped into our GCJ-02 plane, sat/), graded warm; route/pin from sat.json (same projection as the warp)
  satellite: { id: "satellite", land: "#EFECE6", ink: "#3E342B", sub: "#7A6F64", accent: "#9A463D", card: "#FBFAF7" },
  // satellite + flova gpt-image-2.5 edit (satfix/): towers re-rendered true top-down, summer light; crisp HD grade, lighter haze
  satelliteFix: { id: "satelliteFix", land: "#EFECE6", ink: "#3E342B", sub: "#7A6F64", accent: "#9A463D", card: "#FBFAF7" },
  // v6: palette-A Amap base + one flova gpt-image-2.5 edit (2K, frame-239 footprint) using the satellite crop as height/type reference (flova_sat3d/)
  flovaSat3D: { id: "flovaSat3D", land: "#EFECE6", ink: "#483C32", sub: "#8A7F74", accent: "#9A463D", card: "#FBFAF7" },
  // v6b: same edit/alignment; surround re-rendered rich (extruded blocks, trees, edit-matched water) + pyramid blend (flova_sat3d/build_base_v6b.py)
  flovaSat3Db: { id: "flovaSat3Db", land: "#EFECE6", ink: "#483C32", sub: "#8A7F74", accent: "#9A463D", card: "#FBFAF7" },
};
// v6b: plane rect of the GPT edit (flova_sat3d/build.json) – centre of the dolly-time depth-of-field / haze
const EDIT_RECT = [134, -292, 1304, 586];
export const FLOVASAT3D_CREDIT = "示意图　房源照片AI示意　底图据高德数据绘制·AI润色（参考卫星影像）　路线、距离 © 高德地图";
const SATFIX_LAYERS = { wide: { file: "map/satfix_wide.jpg", rect: [-640, -880, 2080, 1960] }, detail: { file: "map/satfix_detail.webp", rect: [-200, -480, 1700, 1100] } };
const SATFIX_CREDIT = "示意图　房源照片AI示意　卫星影像 © Google（AI润色）　路线、距离 © 高德地图";
export const EXT = [-640, -880, 2080, 1960];

// ---------- timeline (frames @30) ----------
export const T = {
  driveEnd: 50,
  scanA: 42, scanB: 62,
  focusA: 78, focusB: 92,
  dollyA: 92, dollyB: 146,
  worldOutA: 104, worldOutB: 134,
  mapInA: 98, mapInB: 130,
  camA: 92, camB: 240,
  morphA: 132, morphB: 152,
  routeA: 156, routeB: 188,
  titleA: 160, metroA: 184,
};
// v3 assemble-then-type-flyin cues (frames). Shells (wordless) first, then glyphs: big title first, small labels last.
export const TF = {
  braces: 156, epBar: 159, distShell: 162, srcShell: 166, metroShell: 180, stationShell: 183,   // phase 1 (3–4f apart)
  title: 166, dist: 169, ep: 172, sub: 176, station: 189, stationSub: 193, src: 196,           // phase 2 block starts
  titleStep: 2, smallStep: 1,
};

const cl = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const seg = (f: number, a: number, b: number, e?: (x: number) => number) => interpolate(f, [a, b], [0, 1], { ...cl, easing: e });
const E_OUT = Easing.bezier(0.16, 1, 0.3, 1);
const E_IO = Easing.bezier(0.65, 0, 0.35, 1);
const backLite = (p: number) => { const c = 0.9; return 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2); }; // ~3% overshoot

// ---------- data ----------
type L = { id: string; community: string; district: string; layout: string; area: number; rent: number; listed: string; tags: string[]; photo: string; photoKind: string; verdict: string };
const MID = DATA.mid as L[];
const CI0 = MID.findIndex((l) => l.id === DATA.chosenId);
const CHOSEN = MID[CI0];
const NSLOT = 12, CI = 9;
const SLOT: L[] = Array.from({ length: NSLOT }, (_, j) => {
  let i = (((j - CI + CI0) % MID.length) + MID.length) % MID.length;
  if (i === CI0 && j !== CI) i = (i + 1) % MID.length;
  return MID[i];
});
const arch = (a: any[]): L => ({ id: a[0], community: a[0], district: "", layout: a[1], area: a[2], rent: a[3], listed: "", tags: [], photo: a[4], photoKind: "stock", verdict: "" });

// ---------- card geometry (uniform everywhere) ----------
const CW = 320, PAD = 14, PW = CW - 2 * PAD, PH = 182, CH = 340, GUT = 48, PITCH = CW + GUT;
const Y0 = 372, OFF = 40;                       // mid row top; alternate cards drop OFF px (reference: (k%2)*40)
const D = 2600;                                 // drive travel at coefficient 1
const K = { bg: 0.35, mid: 0.7, fg: 1.4 };
const midX = (k: number, drive: number) => 720 - CW / 2 + (k - CI) * PITCH + K.mid * (D - drive);
const midY = (k: number) => Y0 + (k % 2 === CI % 2 ? 0 : OFF);
const DRV = { f0: -4, a: 38, b: 50 };            // constant speed then cubic brake with matched entry velocity
const DRV_V = 3 / (3 * (DRV.a - DRV.f0) + (DRV.b - DRV.a)), DRV_PA = DRV_V * (DRV.a - DRV.f0);
const driveAt = (f: number) => {
  if (f <= DRV.a) return D * Math.max(0, DRV_V * (f - DRV.f0));
  const u = Math.min(1, (f - DRV.a) / (DRV.b - DRV.a));
  return D * (DRV_PA + (1 - DRV_PA) * (1 - Math.pow(1 - u, 3)));
};

// ---------- scan targets ----------
const SCAN_Y0 = Y0 - 50, SCAN_Y1 = Y0 + CH + OFF + 40;
const VIS = [CI - 2, CI - 1, CI, CI + 1, CI + 2];
const TARGETS = (() => {
  const rate = (SCAN_Y1 - SCAN_Y0) / (T.scanB - T.scanA);
  const ts = VIS.map((k) => ({ k, bottom: midY(k) + CH, ft: 0 }));
  let prev = -99;
  // rejects fire in scan order (outer first on equal height); the match is always confirmed last
  const order = [...ts].sort((a, b) => Number(a.k === CI) - Number(b.k === CI) || a.bottom - b.bottom || Math.abs(b.k - CI) - Math.abs(a.k - CI));
  for (const t of order) { t.ft = Math.max(T.scanA + (t.bottom - SCAN_Y0) / rate, prev + 2.5); prev = t.ft; }
  return ts;
})();
const chosenFt = TARGETS.find((t) => t.k === CI)!.ft;
export const CUES = { targets: TARGETS.map((t) => t.ft).sort((a, b) => a - b), chosenFt };

// ---------- 3D map camera (proj() mirrors the CSS on <MapPlane>) ----------
export const TY = 60;
const LST = MAP.listing.xy as number[];
const SNAP = [[4, 10, 0, -2], [11, 11, -6.5, -2], [12, 19, -6.5, 0]]; // display-only shift onto road centre (same as koubo ep07), route_m untouched
export const ROUTE = (MAP.route as number[][]).map((p, i) => { const s = SNAP.find((q) => i >= q[0] && i <= q[1]); return s ? [p[0] + s[2], p[1] + s[3]] : p; });
const METRO = (MAP.pois as any[]).find((p) => p.kind === "metro");
export type Cam = { s: number; fx: number; fy: number; tilt: number; P: number };
export const proj = (c: Cam, x: number, y: number) => {
  const th = (c.tilt * Math.PI) / 180;
  const dx = (x - c.fx) * c.s, dy = (y - c.fy) * c.s;
  const X = 720 + dx, Y = 540 + TY + dy * Math.cos(th), Z = dy * Math.sin(th);
  const k = c.P / (c.P - Z);
  return { x: 720 + (X - 720) * k, y: 540 + (Y - 540) * k, k };
};
// camera settles CAM_SETTLE frames before the opener ends (marks land on a still map); END_S widens the final framing
export const CAM_SETTLE = 16, END_S = 1.72;
export const camAt = (f: number): Cam => {
  f = Math.min(f, T.camB - CAM_SETTLE);
  const s = lerp(0.3, END_S, seg(f, T.camA, T.camB - CAM_SETTLE, Easing.bezier(0.5, 0, 0.3, 1)));
  const dz = seg(f, T.camA, 162, E_IO);                         // dolly zoom: lens widens while we push in
  const drift = seg(f, T.morphA, T.camB - CAM_SETTLE, Easing.bezier(0.4, 0, 0.4, 1));
  const mid = [(LST[0] + METRO.xy[0]) / 2 - 10, (LST[1] + METRO.xy[1]) / 2 + 30];
  const tilt = lerp(20, 44, dz) - 6 * seg(f, 156, T.camB - CAM_SETTLE, E_IO);
  return { s, fx: lerp(LST[0], mid[0], drift), fy: lerp(LST[1], mid[1], drift), tilt, P: lerp(4200, 1250, dz) };
};

// ---------- pieces ----------
export const OPENER_NOTES = { on: true };   // set .on = false to hide AI示意/示意 kind tags (brand-strip-only episodes)
const KindTag: React.FC<{ kind: string; scale?: number }> = ({ kind, scale = 1 }) => !OPENER_NOTES.on ? null : (
  <div style={{ position: "absolute", left: 8 * scale, top: 8 * scale, padding: `${2 * scale}px ${7 * scale}px ${3 * scale}px`, borderRadius: 5 * scale, background: "rgba(20,18,20,0.72)", color: "#FBFBF8", fontFamily: SANS, fontWeight: 600, fontSize: 12 * scale, lineHeight: 1.2 }}>
    {kind === "ai" ? "AI示意" : kind === "real" ? "实拍" : "示意"}
  </div>
);

const Price: React.FC<{ v: number; th: Theme; size?: number }> = ({ v, th, size = 30 }) => (
  <span style={{ whiteSpace: "nowrap", color: th.text }}>
    <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: size, fontVariantNumeric: "tabular-nums", letterSpacing: 0.2 }}>{v}</span>
    <span style={{ fontFamily: SANS, fontSize: 13, fontWeight: 500, color: th.sub, marginLeft: 3 }}>元/月</span>
  </span>
);

// card body (everything except the photo) in card-local px; photo slot is (PAD, PAD, PW, PH)
const CardBody: React.FC<{ l: L; th: Theme }> = ({ l, th }) => (
  <>
    <div style={{ position: "absolute", left: PAD, top: PAD + PH + 14, width: PW, display: "flex", alignItems: "baseline", justifyContent: "space-between", fontFamily: SANS }}>
      <div style={{ fontWeight: 700, fontSize: 22, color: th.text, lineHeight: 1.2, whiteSpace: "nowrap" }}>{l.community}</div>
      {l.listed ? <div style={{ fontWeight: 500, fontSize: 13, color: th.mute, whiteSpace: "nowrap" }}>{l.listed}上架</div> : null}
    </div>
    <div style={{ position: "absolute", left: PAD, top: PAD + PH + 50, width: PW, display: "flex", alignItems: "baseline", justifyContent: "space-between", fontFamily: SANS }}>
      <div style={{ fontWeight: 500, fontSize: 16, color: th.sub, whiteSpace: "nowrap" }}>
        {l.layout}<span style={{ margin: "0 7px", color: th.mute }}>·</span><span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 600, fontSize: 19 }}>{l.area}</span>㎡
      </div>
      <Price v={l.rent} th={th} />
    </div>
    <div style={{ position: "absolute", left: PAD, top: PAD + PH + 92, width: PW, height: 1, background: th.hair }} />
    <div style={{ position: "absolute", left: PAD, top: PAD + PH + 104, display: "flex", gap: 6 }}>
      {(l.tags.length ? l.tags : [l.layout.slice(0, 2), "示意"]).slice(0, 3).map((t) => (
        <div key={t} style={{ flexShrink: 0, whiteSpace: "nowrap", padding: "2px 9px 3px", borderRadius: 12, border: `1px solid ${th.chip}`, fontFamily: SANS, fontWeight: 500, fontSize: 12.5, color: th.sub, lineHeight: 1.3 }}>{t}</div>
      ))}
    </div>
  </>
);

const Card: React.FC<{ l: L; th: Theme; x: number; y: number; dim?: number; shadow?: boolean }> = ({ l, th, x, y, dim = 0, shadow = true }) => (
  <div style={{ position: "absolute", left: x, top: y, width: CW, height: CH, borderRadius: 14, background: th.card, border: `1px solid ${th.border}`, boxSizing: "border-box", boxShadow: shadow ? th.shadow : undefined, overflow: "hidden", filter: dim > 0.005 ? (th === LIGHT ? `saturate(${1 - 0.85 * dim}) contrast(${1 - 0.25 * dim}) brightness(${1 + 0.04 * dim})` : `saturate(${1 - 0.8 * dim}) brightness(${1 - 0.45 * dim})`) : undefined, opacity: 1 - (th === LIGHT ? 0.5 : 0.35) * dim }}>
    <div style={{ position: "absolute", left: PAD - 1, top: PAD - 1, width: PW, height: PH, borderRadius: 8, overflow: "hidden" }}>
      <Img src={staticFile(`photos_g/${l.photo}`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      <KindTag kind={l.photoKind} />
    </div>
    <div style={{ position: "absolute", left: -1, top: -1 }}><CardBody l={l} th={th} /></div>
  </div>
);

// background: one coherent archive page — district rows, each split into two groups of 4 uniform cards with a header + count
const PAGE_W = 2900, ROW_Y = [-96, 344, 834], GCOLS = 4, GGAP = 84;
const COLX = (i: number) => 64 + Math.floor(i / GCOLS) * (GCOLS * (CW + 26) - 26 + GGAP) + (i % GCOLS) * (CW + 26);
const ArchivePage: React.FC<{ th: Theme }> = ({ th }) => (
  <div style={{ position: "absolute", left: 0, top: 0, width: PAGE_W, height: 1300 }}>
    {DATA.archive.map((sec: any, si: number) => (
      <React.Fragment key={sec.district}>
        {sec.groups.map((g: any, gi: number) => {
          const x0 = COLX(gi * GCOLS), w = GCOLS * (CW + 26) - 26;
          return (
            <React.Fragment key={gi}>
              <div style={{ position: "absolute", left: x0, top: ROW_Y[si] - 52, width: w, display: "flex", justifyContent: "space-between", alignItems: "baseline", fontFamily: SANS, fontSize: 17, fontWeight: 700, letterSpacing: 2, color: th.sub }}>
                <span>{sec.district}<span style={{ margin: "0 10px", color: th.mute }}>/</span>{g.name}</span>
                <span style={{ letterSpacing: 1, fontWeight: 500 }}><span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 600, fontSize: 20 }}>{g.count}</span> 套</span>
              </div>
              <div style={{ position: "absolute", left: x0, top: ROW_Y[si] - 22, width: w, height: 1, background: th.chip }} />
            </React.Fragment>
          );
        })}
        {sec.items.map((it: any, i: number) => <Card key={i} l={arch(it as any[])} th={th} x={COLX(i)} y={ROW_Y[si]} shadow={false} />)}
      </React.Fragment>
    ))}
  </div>
);

const SearchBar: React.FC<{ th: Theme }> = ({ th }) => (
  <div style={{ width: 560, height: 62, borderRadius: 31, background: th.card, border: `1px solid ${th.border}`, boxSizing: "border-box", boxShadow: th.shadow, display: "flex", alignItems: "center", padding: "0 24px", gap: 14, fontFamily: SANS }}>
    <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke={th.sub} strokeWidth={2} strokeLinecap="round"><circle cx="10.5" cy="10.5" r="6.5" /><path d="M20 20l-4.8-4.8" /></svg>
    <span style={{ fontSize: 19, fontWeight: 500, color: th.mute }}>搜索小区、地铁站、户型</span>
    <span style={{ marginLeft: "auto", fontSize: 15, fontWeight: 600, color: th.sub, padding: "4px 12px", borderRadius: 14, border: `1px solid ${th.chip}` }}>筛选 3</span>
  </div>
);

const Corners: React.FC<{ x: number; y: number; w: number; h: number; s: number; o: number; color: string; flash: number; flashC: string }> = ({ x, y, w, h, s, o, color, flash, flashC }) => {
  const arm = 20, b = `2.5px solid ${color}`, pad = 9;
  const cs: React.CSSProperties[] = [
    { left: 0, top: 0, borderTop: b, borderLeft: b }, { right: 0, top: 0, borderTop: b, borderRight: b },
    { left: 0, bottom: 0, borderBottom: b, borderLeft: b }, { right: 0, bottom: 0, borderBottom: b, borderRight: b },
  ];
  return (
    <div style={{ position: "absolute", left: x - pad, top: y - pad, width: w + 2 * pad, height: h + 2 * pad, opacity: o, transform: `scale(${s})` }}>
      {cs.map((c, i) => <div key={i} style={{ position: "absolute", width: arm, height: arm, ...c }} />)}
      <div style={{ position: "absolute", inset: pad, background: flashC, opacity: flash, borderRadius: 14 }} />
    </div>
  );
};

const TRAIN = '<path d="M21 13c0 -3.87 -3.37 -7 -10 -7h-8" /><path d="M3 15h16a2 2 0 0 0 2 -2" /><path d="M3 6v5h17.5" /><path d="M3 11v4" /><path d="M8 11v-5" /><path d="M13 11v-4.5" /><path d="M3 19h18" />';

export const MapPlane: React.FC<{ c: Cam; o: number; routeP: number; pal: MapPal; route: number[][] }> = ({ c, o, routeP, pal, route }) => {
  const sat = pal.id === "satellite" || pal.id === "satelliteFix";
  const L = pal.id === "satelliteFix" ? SATFIX_LAYERS : SAT.layers;
  const d = route.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");
  return (
    <div style={{ position: "absolute", inset: 0, perspective: c.P, perspectiveOrigin: "720px 540px", opacity: o }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1440, height: 1080, transformOrigin: `${c.fx}px ${c.fy}px`, transform: `translate3d(${720 - c.fx}px, ${540 + TY - c.fy}px, 0) rotateX(${c.tilt}deg) scale(${c.s})` }}>
        {sat ? (
          <>
            {[L.wide, L.detail].map((l) => (
              <Img key={l.file} src={staticFile(l.file)} style={{ position: "absolute", left: l.rect[0], top: l.rect[1], width: l.rect[2] - l.rect[0], height: l.rect[3] - l.rect[1] }} />
            ))}
          </>
        ) : (
          <Img src={staticFile(`map/base_${pal.id}.png`)} style={{ position: "absolute", left: EXT[0], top: EXT[1], width: EXT[2] - EXT[0], height: EXT[3] - EXT[1] }} />
        )}
        <svg width={1440} height={1080} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
          {sat && <path d={d} fill="none" stroke="#1E1C19" strokeOpacity={0.28} strokeWidth={19} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${routeP} 2`} style={{ filter: "blur(3px)" }} />}
          <path d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.95} strokeWidth={sat ? 11 : 13} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${routeP} 2`} />
          <path d={d} fill="none" stroke={pal.accent} strokeWidth={6.5} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${routeP} 2`} />
        </svg>
      </div>
    </div>
  );
};

// single-colour brand mark: the logo file is used as an alpha mask so every logo takes the scene's ink
export const Mono: React.FC<{ file: string; ar: number; h: number; color: string }> = ({ file, ar, h, color }) => {
  const u = `url(${staticFile(file)})`;
  return <div style={{ width: h * ar, height: h, background: color, WebkitMaskImage: u, maskImage: u, WebkitMaskSize: "100% 100%", maskSize: "100% 100%", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat" }} />;
};

// ---------- main ----------
export const Opener: React.FC<{ theme?: "dark" | "light"; map?: "A" | "B" | "flovaA" | "satellite" | "satelliteFix" | "flovaSat3D" | "flovaSat3Db"; strip?: boolean; chrome?: boolean; drawRoute?: boolean; metroMark?: boolean }> = ({ theme = "light", map = "A", strip = true, chrome = true, drawRoute = true, metroMark = true }) => {
  const th = theme === "light" ? LIGHT : DARK;
  const pal = MAP_PALS[map];
  const isSat = map === "satellite" || map === "satelliteFix";
  const isFix = map === "satelliteFix";                          // lighter haze so the HD imagery reads clearly
  const route = isSat ? (SAT.route as number[][]) : ROUTE;      // sat: un-snapped Amap polyline in the warp's projection
  const lst = isSat ? SAT.listing : LST, metXY = isSat ? SAT.metro : METRO.xy;
  const MAPI = { ink: pal.ink, accent: pal.accent, grey: pal.sub, paper: pal.ink };
  const f = useCurrentFrame();
  const drive = driveAt(f);

  // focus / dolly
  const focus = seg(f, T.focusA, T.focusB, E_OUT);
  const dolly = seg(f, T.dollyA, T.dollyB, Easing.bezier(0.45, 0, 0.3, 1));
  const worldScale = 1 + 1.4 * dolly;
  const worldBlur = 9 * dolly;
  const worldO = 1 - seg(f, T.worldOutA, T.worldOutB);
  const othersDim = seg(f, T.focusA - 4, T.focusB + 4, E_OUT);
  const toDark = seg(f, T.worldOutA - 4, T.worldOutB - 6);  // stage + chrome ink fade to the dark map act

  // chosen card -> hero
  const kHero = 540 / CW;
  const restX = midX(CI, drive), restY = midY(CI);
  const kNow = lerp(1, kHero, focus);
  const heroCx = lerp(restX + CW / 2, 720, focus), heroCy = lerp(restY + CH / 2, 540, focus);
  const cardL = heroCx - (CW * kNow) / 2, cardT = heroCy - (CH * kNow) / 2;

  // map camera + pin
  const cam = camAt(f);
  const mapO = seg(f, T.mapInA, T.mapInB, Easing.bezier(0.3, 0, 0.4, 1));
  const routeP = !drawRoute ? 0 : seg(f, T.routeA, T.routeB, Easing.bezier(0.45, 0, 0.25, 1));
  const G = proj(cam, lst[0], lst[1]);
  const HEAD = 88, HOFF = { x: 82, y: -58 };           // photo head sits up-right of the ground point, clear of the route start
  const headX = G.x + HOFF.x, headY = G.y + HOFF.y;
  const metro = proj(cam, metXY[0], metXY[1]);
  const rMid = route[Math.floor(route.length * 0.6)];
  const rLab = proj(cam, rMid[0], rMid[1]);

  // morph: shell dissolves first, then the photo rect travels on an arc and rounds into the circular head
  const mp = seg(f, T.morphA, T.morphB, E_IO);
  const shellO = 1 - seg(f, T.morphA, T.morphA + 7, Easing.out(Easing.quad));
  const ph0 = { cx: cardL + (PAD + PW / 2) * kNow, cy: cardT + (PAD + PH / 2) * kNow, w: PW * kNow, h: PH * kNow };
  const pw = lerp(ph0.w, HEAD, mp), phh = lerp(ph0.h, HEAD, Math.pow(mp, 0.8));
  const pcx = lerp(ph0.cx, headX, mp), pcy = lerp(ph0.cy, headY, mp) - 34 * Math.sin(Math.PI * mp) * (1 - mp);
  const prad = lerp(8 * kNow, Math.min(pw, phh) / 2, Math.pow(mp, 1.3));
  const ring = 4 * seg(f, T.morphA + 6, T.morphB);
  const landP = seg(f, T.morphB, T.morphB + 8);
  const squash = 1 - 0.04 * Math.sin(Math.PI * landP);        // ≤4% squash, 8-frame settle
  const leader = seg(f, T.morphB - 2, T.morphB + 6, E_OUT);
  const rip = seg(f, T.morphB, T.morphB + 22, Easing.out(Easing.quad));

  // scanline
  const scanP = seg(f, T.scanA, T.scanB);
  void scanP; // scanline visual removed (v6c)
  const fired = TARGETS.filter((t) => f >= t.ft).length;
  const scanDone = f >= chosenFt + 8;

  // chrome
  const chromeO = 1 - seg(f, T.focusA, T.focusA + 8);
  const counter = Math.round(lerp(DATA.candidates, 5, seg(f, 4, T.driveEnd, Easing.bezier(0.3, 0, 0.2, 1))));
  const statusO = seg(f, T.scanA - 2, T.scanA + 4) * (1 - seg(f, T.focusB, T.focusB + 8));
  const ink = interpolateColors(toDark, [0, 1], [th.text, pal.ink]);
  const inkSub = interpolateColors(toDark, [0, 1], [th.sub, pal.sub]);
  const mapTag = seg(f, T.mapInB - 10, T.mapInB);
  const stage = interpolateColors(toDark, [0, 1], [th.stage, pal.land]);

  return (
    <AbsoluteFill style={{ background: stage, overflow: "hidden" }}>
      {/* ===== map act (behind), rises during the dolly ===== */}
      {f >= T.mapInA - 1 && <MapPlane c={cam} o={mapO} routeP={routeP} pal={pal} route={route} />}
      {/* v6b: during the dolly the outer (code-drawn) map recedes – soft blur + paper haze outside an ellipse around the edit,
          so the rich centre reads as the focal plane (depth of field), not a pasted patch. Fully gone by frame 176. */}
      {map === "flovaSat3Db" && f >= T.mapInA - 1 && (() => {
        const dof = seg(f, 112, 126, E_IO) * (1 - seg(f, 156, 176, E_IO));
        if (dof <= 0.001) return null;
        const cs = [[EDIT_RECT[0], EDIT_RECT[1]], [EDIT_RECT[2], EDIT_RECT[1]], [EDIT_RECT[0], EDIT_RECT[3]], [EDIT_RECT[2], EDIT_RECT[3]]].map((q) => proj(cam, q[0], q[1]));
        const xs = cs.map((q) => q.x), ys = cs.map((q) => q.y);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2 + 10;
        const rx = ((Math.max(...xs) - Math.min(...xs)) / 2) * 1.02, ry = ((Math.max(...ys) - Math.min(...ys)) / 2) * 1.08;
        const g = (a: number) => Math.round(a * dof * 255).toString(16).padStart(2, "0");
        const mask = `radial-gradient(ellipse ${rx}px ${ry}px at ${cx}px ${cy}px, #0000 0%, #0000 62%, #000 112%)`;
        return (
          <>
            <AbsoluteFill style={{ backdropFilter: `blur(${2.4 * dof}px)`, WebkitBackdropFilter: `blur(${2.4 * dof}px)`, maskImage: mask, WebkitMaskImage: mask }} />
            <AbsoluteFill style={{ background: `radial-gradient(ellipse ${rx}px ${ry}px at ${cx}px ${cy}px, ${pal.land}00 0%, ${pal.land}00 66%, ${pal.land}${g(0.22)} 96%, ${pal.land}${g(0.5)} 135%)` }} />
          </>
        );
      })()}
      {f >= T.mapInA - 1 && (
        <AbsoluteFill style={{ opacity: mapO, background: isFix ? `linear-gradient(180deg, ${pal.land}F0 0%, ${pal.land}A0 9%, ${pal.land}00 25%, ${pal.land}00 66%, ${pal.land}C8 93%)` : `linear-gradient(180deg, ${pal.land} 0%, ${pal.land}D0 12%, ${pal.land}00 34%, ${pal.land}00 62%, ${pal.land}E0 92%)` }} />
      )}
      {/* satellite: soft paper wash behind the title block + source line so the type-flyin stays readable on imagery */}
      {isSat && f >= T.mapInA - 1 && (
        <AbsoluteFill style={{ opacity: mapO * (0.55 + 0.45 * seg(f, TF.braces - 10, TF.braces + 6, E_IO)), background: isFix ? `radial-gradient(ellipse 760px 300px at 330px 885px, ${pal.land}E8 0%, ${pal.land}A8 45%, ${pal.land}00 100%), radial-gradient(ellipse 540px 110px at 1180px 1035px, ${pal.land}C8 0%, ${pal.land}00 100%)` : `radial-gradient(ellipse 820px 330px at 330px 880px, ${pal.land}F2 0%, ${pal.land}C8 45%, ${pal.land}00 100%), radial-gradient(ellipse 560px 120px at 1180px 1035px, ${pal.land}D8 0%, ${pal.land}00 100%)` }} />
      )}

      {/* ===== card world: archive page (0.35) / card row (0.7) / sparse foreground (1.4) ===== */}
      {worldO > 0.001 && (
        <AbsoluteFill style={{ transform: `scale(${worldScale})`, transformOrigin: "720px 540px", filter: worldBlur > 0.05 ? `blur(${worldBlur}px)` : undefined, opacity: worldO }}>
          <div style={{ position: "absolute", inset: 0, transform: `translateX(${-drive * K.bg}px) scale(1.05)`, transformOrigin: "720px 540px", filter: th.bgFilter, opacity: th.bgO * (1 - 0.35 * othersDim) }}>
            <ArchivePage th={th} />
          </div>
          <AbsoluteFill style={{ filter: othersDim > 0.01 ? `blur(${3.5 * othersDim}px)` : undefined }}>
            {SLOT.map((l, k) => {
              if (k === CI) return null;
              const x = midX(k, drive);
              if (x < -CW - 40 || x > 1480) return null;
              const tg = TARGETS.find((t) => t.k === k);
              const dim = tg ? seg(f, tg.ft + 3, tg.ft + 10, E_OUT) * 0.7 + 0.3 * othersDim : 0.5 * seg(f, T.scanA, T.scanB);
              return <Card key={k} l={l} th={th} x={x} y={midY(k)} dim={Math.min(1, dim)} />;
            })}
          </AbsoluteFill>
          <div style={{ position: "absolute", inset: 0, transform: `translateX(${-drive * K.fg}px)`, filter: "blur(3px)" }}>
            <div style={{ position: "absolute", left: 980, top: 196 }}><SearchBar th={th} /></div>
            <div style={{ position: "absolute", left: 2780, top: 0, transform: "scale(1.12)", transformOrigin: "0 0" }}><Card l={arch(DATA.fgCard)} th={th} x={0} y={770} /></div>
          </div>
          {/* scan annotations (non-chosen) */}
          {TARGETS.filter((t) => t.k !== CI).map((t) => {
            const a = seg(f, t.ft, t.ft + 6, E_OUT);
            if (a <= 0) return null;
            const s = lerp(1.75, 1, backLite(seg(f, t.ft, t.ft + 7)));
            const flash = 0.08 * seg(f, t.ft + 1, t.ft + 3) * (1 - seg(f, t.ft + 3, t.ft + 7));
            const la = seg(f, t.ft + 2, t.ft + 8, E_OUT) * (1 - othersDim);
            const x = midX(t.k, drive), y = midY(t.k);
            const lx = Math.min(Math.max(x, 40), 1440 - 40 - 170);
            return (
              <React.Fragment key={t.k}>
                <Corners x={x} y={y} w={CW} h={CH} s={s} o={Math.min(1, a * 1.6) * (1 - othersDim) * 0.85} color={th.corner} flash={flash} flashC={th.text} />
                <div style={{ position: "absolute", left: lx, top: y - 44, opacity: la, transform: `translateY(${lerp(6, 0, la)}px)`, fontFamily: SANS, fontWeight: 600, fontSize: 18, color: th.sub, whiteSpace: "nowrap", letterSpacing: 1 }}>
                  <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 600, marginRight: 8, color: th.mute }}>{String(VIS.indexOf(t.k) + 1).padStart(2, "0")}</span>{SLOT[t.k].verdict}
                </div>
              </React.Fragment>
            );
          })}
        </AbsoluteFill>
      )}

      {/* app-header wash so the chrome reads over the archive page (fades with the card world) */}
      <AbsoluteFill style={{ opacity: worldO, background: `linear-gradient(180deg, ${th.stage} 0%, ${th.stage}E6 120px, ${th.stage}00 200px)` }} />

      {/* ===== scanline removed in v6c (user request): annotations/selection unchanged ===== */}

      {/* ===== the chosen listing: one continuous element (card -> hero -> photo pin) ===== */}
      {(() => {
        const a = seg(f, chosenFt, chosenFt + 6, E_OUT);
        const s = lerp(1.75, 1, backLite(seg(f, chosenFt, chosenFt + 7)));
        const flash = 0.08 * seg(f, chosenFt + 1, chosenFt + 3) * (1 - seg(f, chosenFt + 3, chosenFt + 7));
        const cornO = f >= chosenFt ? Math.min(1, a * 1.6) * (1 - seg(f, T.focusA - 2, T.focusA + 4)) : 0;
        const la = seg(f, chosenFt + 2, chosenFt + 8, E_OUT) * (1 - seg(f, T.focusA - 2, T.focusA + 4));
        const shK = Math.max(focus, 0) * (1 - mp);
        return (
          <>
            {/* ground dot, ripple and leader (after landing) */}
            {f >= T.morphB - 2 && (
              <svg width={1440} height={1080} style={{ position: "absolute", left: 0, top: 0 }}>
                <ellipse cx={G.x} cy={G.y} rx={14 + 80 * rip} ry={(14 + 80 * rip) * 0.5} fill="none" stroke={MAPI.accent} strokeWidth={2.5} opacity={0.85 * (1 - rip)} />
                <line x1={G.x} y1={G.y} x2={lerp(G.x, headX - HEAD * 0.33, leader)} y2={lerp(G.y, headY + HEAD * 0.36, leader)} stroke={pal.ink} strokeWidth={2.5} strokeLinecap="round" />
                <ellipse cx={G.x} cy={G.y} rx={8} ry={4.5} fill={MAPI.accent} stroke={MAPI.ink} strokeWidth={1.5} opacity={leader} />
              </svg>
            )}
            {/* card shell (bg + text), pinned during dolly, dissolves at morph start */}
            {shellO > 0 && (
              <div style={{ position: "absolute", left: cardL, top: cardT, width: CW, height: CH, transform: `scale(${kNow})`, transformOrigin: "0 0", opacity: shellO }}>
                <div style={{ position: "absolute", inset: 0, borderRadius: 14, background: th.card, border: `1px solid ${th.border}`, boxSizing: "border-box", boxShadow: shK > 0.01 ? th.shadowHero : th.shadow }} />
                <div style={{ position: "absolute", left: 0, top: 0, opacity: 1 - seg(f, T.morphA - 2, T.morphA + 4) }}><CardBody l={CHOSEN} th={th} /></div>
              </div>
            )}
            {/* the photo itself: never fades, it becomes the pin head */}
            <div style={{ position: "absolute", left: pcx - pw / 2, top: pcy - phh / 2, width: pw, height: phh, borderRadius: prad, overflow: "hidden", boxShadow: `0 0 0 ${ring}px #FFFFFF${mp > 0.5 ? ", 0 10px 24px rgba(31,28,23,0.35)" : ""}`, transform: `scale(${1 / squash}, ${squash})`, transformOrigin: "50% 100%" }}>
              <Img src={staticFile(`photos_g/${CHOSEN.photo}`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              <div style={{ opacity: 1 - seg(f, T.morphA, T.morphA + 6) }}><KindTag kind={CHOSEN.photoKind} scale={kNow} /></div>
            </div>
            {OPENER_NOTES.on && f >= T.morphB && (
              <div style={{ position: "absolute", left: headX + HEAD / 2 - 14, top: headY - HEAD / 2 - 6, opacity: seg(f, T.morphB + 2, T.morphB + 8), padding: "1px 6px 2px", borderRadius: 4, background: "rgba(20,18,20,0.72)", color: "#FBFBF8", fontFamily: SANS, fontWeight: 600, fontSize: 11 }}>AI示意</div>
            )}
            {cornO > 0 && <Corners x={restX} y={restY} w={CW} h={CH} s={s} o={cornO} color={th === LIGHT ? th.text : MAPI.accent} flash={flash} flashC={th.text} />}
            {la > 0 && (
              <div style={{ position: "absolute", left: restX - 9, top: restY - 50, opacity: la, transform: `translateY(${lerp(6, 0, la)}px)`, padding: "3px 10px 4px", borderRadius: 4, background: th.chosenBg, color: th.chosenInk, fontFamily: SANS, fontWeight: 700, fontSize: 18, whiteSpace: "nowrap" }}>
                <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, marginRight: 8, color: th === LIGHT ? MAPI.accent : th.chosenInk }}>{String(VIS.indexOf(CI) + 1).padStart(2, "0")}</span>{CHOSEN.verdict}
              </div>
            )}
          </>
        );
      })()}

      {/* ===== map labels (assemble-then-type-flyin: shells fly flat, then glyphs fly in 3D) ===== */}
      {drawRoute && f >= TF.distShell && (
        <div style={{ position: "absolute", right: Math.min(1440 - rLab.x + 26, 1440 - 60 - 230), top: rLab.y - 30, padding: "6px 14px 8px" }}>
          <div style={{ position: "absolute", inset: 0, borderRadius: 10, background: pal.card, border: `1px solid ${LIGHT.border}`, boxShadow: LIGHT.shadow, ...shellStyle(f, [-150, 40], -4, TF.distShell) }} />
          <FlyText seed={100} start={TF.dist} step={TF.smallStep} style={{ position: "relative", display: "flex", alignItems: "baseline" }} runs={[
            { s: "距地铁站", style: { fontFamily: SANS, fontWeight: 600, fontSize: 18, color: MAPI.grey, marginRight: 8 } },
            { node: <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 40, color: MAPI.accent, fontVariantNumeric: "tabular-nums", lineHeight: 1, display: "inline-block", minWidth: 62, textAlign: "right" }}>{Math.round(Number(MAP.route_m) * routeP)}</span>, style: { marginRight: 8 } },
            { s: "米", style: { fontFamily: SANS, fontWeight: 600, fontSize: 18, color: pal.ink } },
          ]} />
        </div>
      )}
      {metroMark && f >= TF.metroShell && (
        <>
          <div style={{ position: "absolute", left: metro.x - 26, top: metro.y - 26, width: 52, height: 52, borderRadius: 26, background: pal.card, border: `1px solid ${LIGHT.border}`, boxShadow: LIGHT.shadow, display: "flex", alignItems: "center", justifyContent: "center", ...shellStyle(f, [-90, -130], -6, TF.metroShell) }}>
            <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke={MAPI.ink} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: TRAIN }} />
          </div>
          <div style={{ position: "absolute", left: metro.x + 38, top: metro.y - 30, padding: "6px 14px 8px" }}>
            <div style={{ position: "absolute", inset: 0, borderRadius: 10, background: pal.card, border: `1px solid ${LIGHT.border}`, boxShadow: LIGHT.shadow, ...shellStyle(f, [170, -60], 5, TF.stationShell) }} />
            <div style={{ position: "relative" }}>
              <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: 24, color: pal.ink, lineHeight: 1.2 }}><FlyText seed={140} start={TF.station} step={TF.smallStep} runs={[{ s: METRO.name }]} /></div>
              <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 17, color: MAPI.grey, lineHeight: 1.3 }}><FlyText seed={160} start={TF.stationSub} step={TF.smallStep} runs={[{ s: METRO.sub }]} /></div>
            </div>
          </div>
        </>
      )}

      {/* ===== title block ===== */}
      {f >= TF.braces && (() => {
        const numS: React.CSSProperties = { fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 44 };
        const s1 = TF.sub, s2 = s1 + CHOSEN.layout.length * TF.smallStep + 3, s3 = s2 + (String(CHOSEN.area).length + 1) * TF.smallStep + 3;
        return (
          <div style={{ position: "absolute", left: 96, top: 760 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: SANS, fontWeight: 600, fontSize: 19, color: pal.sub, letterSpacing: 1 }}>
              <div style={{ width: 28, height: 3, borderRadius: 2, background: MAPI.accent, ...shellStyle(f, [-180, 0], 0, TF.epBar) }} />
              <FlyText seed={60} start={TF.ep} step={TF.smallStep} runs={[{ s: "@贝壳-TV" }, { s: "EP.07", style: { fontFamily: NUM, fontStyle: "italic", marginLeft: 12 } }]} />
            </div>
            <div style={{ display: "flex", alignItems: "center", marginTop: 4, fontFamily: TITLE, fontWeight: 700, fontSize: 84, color: pal.ink, lineHeight: 1.1 }}>
              <span style={{ display: "inline-block", color: MAPI.accent, ...shellStyle(f, [-220, 30], -8, TF.braces) }}>{"{"}</span>
              <FlyText seed={0} start={TF.title} step={TF.titleStep} style={{ margin: "0 14px" }} runs={[{ s: CHOSEN.community }]} />
              <span style={{ display: "inline-block", color: MAPI.accent, ...shellStyle(f, [220, -30], 8, TF.braces + 2) }}>{"}"}</span>
            </div>
            <div style={{ marginTop: 6, fontFamily: SANS, fontWeight: 600, fontSize: 30, color: pal.ink, display: "flex", gap: 22, alignItems: "baseline" }}>
              <FlyText seed={20} start={s1} step={TF.smallStep} runs={[{ s: CHOSEN.layout }]} />
              <FlyText seed={30} start={s2} step={TF.smallStep} runs={[{ s: String(CHOSEN.area), style: numS }, { s: "㎡" }]} />
              <FlyText seed={40} start={s3} step={TF.smallStep} runs={[{ s: String(CHOSEN.rent), style: { ...numS, color: MAPI.accent } }, { s: "元/月" }]} />
            </div>
          </div>
        );
      })()}

      {/* v6d: map-end 贝壳 source line removed – the persistent footer strip is the only brand/source mark */}
      {/* ===== data-source footer (v6d): 贝壳 source mark + mono brand row, visible for the whole opener (frames 0–239);
           wash/ink follow the stage -> map transition so it stays readable over the map ===== */}
      {strip && (() => {
        const p = (_i: number) => 1;   // v6d: on screen from frame 0 to 239 (no entrance stagger)
        const it = (i: number, extra?: React.CSSProperties): React.CSSProperties => ({ opacity: p(i), ...extra });
        const hx = (h: string) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
        const w0 = hx(th.stage), w1 = hx(pal.land), wc = w0.map((v, k) => Math.round(lerp(v, w1[k], toDark))).join(",");
        const wash = (a: number) => `rgba(${wc},${a})`;
        const muteC = interpolateColors(toDark, [0, 1], [th.mute, pal.sub]);
        const ruleC = interpolateColors(toDark, [0, 1], [th.chip, "rgba(138,127,116,0.33)"]);
        return (
          <>
            <AbsoluteFill style={{ background: `linear-gradient(0deg, ${wash(1)} 0%, ${wash(0.93)} 70px, ${wash(0)} ${lerp(165, 150, toDark)}px)` }} />
            <div style={{ position: "absolute", left: 60, right: 60, bottom: 38, height: 30, display: "flex", alignItems: "center", fontFamily: SANS }}>
              <div style={it(0)}><Mono file={BRANDS.sourceMark.file} ar={BRANDS.sourceMark.ar} h={26} color={inkSub} /></div>
              <div style={it(0, { marginLeft: 12, fontSize: 15, fontWeight: 600, color: inkSub, letterSpacing: 1, whiteSpace: "nowrap" })}>{BRANDS.sourceMark.label}</div>
              <div style={it(1, { width: 1, height: 22, background: ruleC, margin: "0 24px" })} />
              <div style={it(1, { fontSize: 13, fontWeight: 500, color: muteC, letterSpacing: 1, marginRight: 22, whiteSpace: "nowrap" })}>{BRANDS.rowLabel}</div>
              {BRANDS.row.map((b, i) => (
                <div key={b.name} style={it(2 + i, { marginRight: 30, opacity: 0.5 * p(2 + i) })}><Mono file={b.file} ar={b.ar} h={b.h} color={ink} /></div>
              ))}
              <div style={it(6, { marginLeft: "auto", fontSize: 13, fontWeight: 500, color: muteC, letterSpacing: 1, whiteSpace: "nowrap" })}>房源卡片为示例数据 · 非实时房源</div>
            </div>
          </>
        );
      })()}

      {/* ===== chrome ===== */}
      <div style={{ position: "absolute", left: 60, top: 54, display: chrome ? "flex" : "none", gap: 12, alignItems: "center" }}>
        <div style={{ padding: "3px 10px 4px", borderRadius: 6, border: `1.5px solid ${ink}`, opacity: 0.85, color: ink, fontFamily: SANS, fontWeight: 700, fontSize: 15 }}>{DATA.sampleTag}</div>
        <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 14, color: inkSub }}>
          {mapTag > 0.5 ? (isFix ? SATFIX_CREDIT : isSat ? SAT.credit : (map === "flovaSat3D" || map === "flovaSat3Db") ? FLOVASAT3D_CREDIT : "示意图　房源照片AI示意　底图据高德数据绘制　路线、距离 © 高德地图") : "房源照片为AI示意或图库示意"}
        </div>
      </div>
      <div style={{ position: "absolute", left: 60, top: 96, display: "flex", gap: 8, opacity: chromeO }}>
        {DATA.filters.map((t, i) => {
          const p = seg(f, 2 + i * 3, 10 + i * 3, E_OUT);
          return <div key={t} style={{ opacity: p, transform: `translateY(${lerp(12, 0, p)}px)`, padding: "5px 14px 7px", borderRadius: 18, background: th.card, border: `1px solid ${th.border}`, boxShadow: th.shadow, color: th.text, fontFamily: SANS, fontWeight: 600, fontSize: 19 }}>{t}</div>;
        })}
      </div>
      <div style={{ position: "absolute", right: 60, top: 50, textAlign: "right", opacity: chromeO * seg(f, 4, 12) }}>
        <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 15, color: th.sub, letterSpacing: 1 }}>候选房源</div>
        <div style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 60, color: th.text, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{scanDone ? 1 : counter}<span style={{ fontFamily: SANS, fontStyle: "normal", fontWeight: 600, fontSize: 18, marginLeft: 4, color: th.sub }}>套</span></div>
      </div>
      {statusO > 0 && (
        <div style={{ position: "absolute", left: 0, width: 1440, top: 64, textAlign: "center", opacity: statusO, fontFamily: NUM, fontStyle: "italic", fontWeight: 600, fontSize: 22, letterSpacing: 3, color: scanDone ? (th === LIGHT ? th.text : MAPI.accent) : th.sub }}>
          {scanDone ? <span style={{ fontFamily: SANS, fontStyle: "normal", fontWeight: 700, letterSpacing: 2 }}>匹配 1 套</span> : `SCAN ${String(fired).padStart(2, "0")}/${String(TARGETS.length).padStart(2, "0")}`}
        </div>
      )}
    </AbsoluteFill>
  );
};
