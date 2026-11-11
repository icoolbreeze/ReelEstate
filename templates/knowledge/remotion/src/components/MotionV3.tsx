// MotionV3 — light editorial kit for the knowledge series (v4 redesign, 2026-10-14).
// Design read: Beike platform explainer for Douyin / 视频号 renters and landlords; light paper canvas,
// one Beike-blue accent, MediaStorm timing. Motion grammar re-skinned from shotcraft (Apache-2.0):
// blur-slide chapter titles, count-up settle stats, pin-drop map, draw-on process flow, list reveal,
// logo wall settle. No neon / glass stack / purple glow / particles; every number traces to research.md.
// v4b: purple / off-white / yellow palette + custom FX (MotionFX.tsx).
// RULE: never render internal file names / paths / source labels on screen.
import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { NUM, SANS, TITLE } from "../fonts";
import { E_OUT, backLite, lerp, seg } from "../lib";

export const W = 1440, H = 1080;

// ---------- palette (single accent: Beike blue; ink is off-navy, never pure black) ----------
export const C = {
  ink: "#24173F",
  sub: "#6E6585",
  blue: "#6D3BEB",
  blueDeep: "#4A22B5",
  blueSoft: "#F0EAFF",
  blueLine: "rgba(109,59,235,0.28)",
  yellow: "#FFC83D",
  yellowDeep: "#E9A800",
  paper: "#FBF8F1",
  card: "#FFFFFF",
  cardInk: "#20293B",
  shadow: "0 18px 44px rgba(36,23,63,0.12), 0 3px 10px rgba(36,23,63,0.07)",
  shadowSm: "0 8px 22px rgba(36,23,63,0.10)",
};

// ---------- light paper background: pale blue wash + two faint washes, deterministic ----------
export const PaperBg: React.FC<{ tint?: number }> = ({ tint = 1 }) => (
  <AbsoluteFill style={{ background: `linear-gradient(168deg,#F2ECFF 0%,#FBF8F1 46%,#FFFFFF 100%)` }}>
    <div style={{ position: "absolute", left: -220, top: -260, width: 720, height: 720, borderRadius: 360, background: "radial-gradient(circle,rgba(109,59,235,0.10) 0%,rgba(109,59,235,0) 70%)", opacity: tint }} />
    <div style={{ position: "absolute", right: -280, bottom: -300, width: 820, height: 820, borderRadius: 410, background: "radial-gradient(circle,rgba(109,59,235,0.07) 0%,rgba(109,59,235,0) 70%)", opacity: tint }} />
  </AbsoluteFill>
);

// ---------- chapter title (blur-slide): blue kicker bar + heavy title + quiet subtitle ----------
export const ChapterTitle: React.FC<{ kicker?: string; title: string; sub?: string; x?: number; y?: number; align?: "left" | "center"; start?: number }> = ({ kicker, title, sub, x = 88, y = 96, align = "left", start = 0 }) => {
  const f = useCurrentFrame();
  const qa = seg(f, start, start + 12, E_OUT);
  const qt = seg(f, start + 5, start + 19, E_OUT);
  const qs = seg(f, start + 12, start + 24, E_OUT);
  const center = align === "center";
  return (
    <div style={{ position: "absolute", left: center ? 0 : x, top: y, width: W, paddingLeft: center ? 0 : x, paddingRight: center ? 0 : x, textAlign: center ? "center" : "left" }}>
      {kicker && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: center ? "center" : "flex-start", gap: 12, opacity: qa, transform: `translateY(${lerp(16, 0, qa)}px)` }}>
          <span style={{ display: "inline-block", width: 34, height: 8, borderRadius: 4, background: C.blue }} />
          <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 700, fontSize: 26, letterSpacing: 4, color: C.blueDeep }}>{kicker}</span>
        </div>
      )}
      <div style={{ marginTop: 12, fontFamily: TITLE, fontWeight: 700, fontSize: 76, lineHeight: 1.08, color: C.ink, opacity: qt, transform: `translateY(${lerp(26, 0, qt)}px)`, letterSpacing: 1 }}>{title}</div>
      {sub && <div style={{ marginTop: 14, fontFamily: SANS, fontWeight: 500, fontSize: 30, color: C.sub, opacity: qs, transform: `translateY(${lerp(18, 0, qs)}px)` }}>{sub}</div>}
    </div>
  );
};

// ---------- count-up number (no odometer glyph roll: clean settle, ≤4% overshoot via scale) ----------
const CountNum: React.FC<{ value: string; local: number; start: number; dur?: number; fontSize?: number }> = ({ value, local, start, dur = 26, fontSize = 92 }) => {
  const m = value.match(/^([\d.]+)(.*)$/);
  const num = m ? parseFloat(m[1]) : 0;
  const suffix = m ? m[2] : value;
  const dec = m && m[1].includes(".") ? 1 : 0;
  const p = seg(local, start, start + dur, E_OUT);
  const s = backLite(seg(local, start, start + 14));
  const shown = (num * p).toFixed(dec);
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", transform: `scale(${lerp(0.94, 1, s)})`, transformOrigin: "0 80%" }}>
      <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize, lineHeight: 1, color: C.blue, fontVariantNumeric: "tabular-nums" }}>{shown}</span>
      <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: fontSize * 0.46, color: C.blueDeep, marginLeft: 4 }}>{suffix}</span>
    </span>
  );
};

// ---------- compact stat card (right rail): big count left, label + source right; stays above caption band ----------
export const StatCard: React.FC<{ value: string; label: string; note: string; local: number; start: number; w?: number }> = ({ value, label, note, local, start, w = 492 }) => {
  const q = seg(local, start, start + 11, E_OUT);
  const s = backLite(seg(local, start, start + 13));
  return (
    <div style={{ width: w, opacity: q, transform: `translateX(${lerp(48, 0, q)}px) scale(${lerp(0.97, 1, s)})`, display: "flex", alignItems: "center", gap: 24, background: C.card, borderRadius: 18, boxShadow: C.shadow, border: "1px solid rgba(36,23,63,0.06)", padding: "16px 26px 16px 22px" }}>
      <span style={{ width: 8, alignSelf: "stretch", borderRadius: 4, background: `linear-gradient(180deg,${C.blue},#FFC83D)` }} />
      <span style={{ minWidth: 190 }}><CountNum value={value} local={local} start={start + 3} fontSize={64} /></span>
      <span>
        <span style={{ display: "block", fontFamily: SANS, fontWeight: 800, fontSize: 28, color: C.ink, lineHeight: 1.15 }}>{label}</span>
        <span style={{ display: "block", fontFamily: SANS, fontWeight: 500, fontSize: 19, color: C.sub, marginTop: 4 }}>{note}</span>
      </span>
    </div>
  );
};

// ---------- real app screenshot inside a phone, animated scroll + tap ripple ----------
export const PhoneX: React.FC<{ img: string; local: number; x: number; y: number; h: number; imgRatio: number; scrollFrom?: number; scrollTo?: number; tapAt?: number | null; enterAt?: number; scrollDur?: number }> = ({ img, local, x, y, h, imgRatio, scrollFrom = 0, scrollTo = 0.16, tapAt = null, enterAt = 0, scrollDur = 90 }) => {
  const pw = h * 0.487;
  const sw = pw - 22, sh = h - 22;
  const imgW = sw, imgH = sw / imgRatio;
  const maxScroll = Math.max(0, imgH - sh);
  const q = seg(local, enterAt, enterAt + 14, E_OUT);
  const p = seg(local, enterAt + 18, enterAt + 18 + scrollDur, (x: number) => x * x * (3 - 2 * x));
  const sy = -lerp(scrollFrom, scrollTo, p) * maxScroll;
  const tap = tapAt != null ? seg(local, tapAt, tapAt + 4) * (1 - seg(local, tapAt + 4, tapAt + 18)) : 0;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: pw, height: h, opacity: q, transform: `translateY(${lerp(60, 0, q)}px) scale(${lerp(0.96, 1, q)})` }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: 48, background: "#1B1530", boxShadow: "0 34px 70px rgba(36,23,63,0.28), 0 6px 16px rgba(36,23,63,0.16)" }} />
      <div style={{ position: "absolute", left: 11, top: 11, width: sw, height: sh, borderRadius: 36, overflow: "hidden", background: "#FFF" }}>
        <Img src={staticFile(img)} style={{ position: "absolute", left: 0, top: sy, width: imgW, height: imgH }} />
        {tap > 0 && <div style={{ position: "absolute", left: sw * 0.5 - 34, top: sh * 0.42 - 34, width: 68, height: 68, borderRadius: 34, border: "4px solid rgba(109,59,235,0.9)", opacity: tap, transform: `scale(${lerp(0.4, 1.5, 1 - tap)})` }} />}
      </div>
      <div style={{ position: "absolute", left: pw / 2 - 44, top: 22, width: 88, height: 10, borderRadius: 5, background: "#1B1530" }} />
    </div>
  );
};

// ---------- category pill (租房 / 二手房 / 新房 + VR) ----------
export const CategoryPills: React.FC<{ local: number; outAt: number }> = ({ local, outAt }) => {
  const items = [
    { t: "租房", d: "整租 · 合租" },
    { t: "二手房", d: "真房源核验" },
    { t: "新房", d: "楼盘一手信息" },
  ];
  const qo = 1 - seg(local, outAt, outAt + 10, E_OUT);
  return (
    <div style={{ position: "absolute", left: 856, top: 252, width: 504, opacity: qo }}>
      {items.map((it, i) => {
        const st = 30 + i * 12;
        const q = seg(local, st, st + 10, E_OUT);
        return (
          <div key={it.t} style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 18, opacity: q, transform: `translateX(${lerp(46, 0, q)}px)` }}>
            <div style={{ width: 50, height: 50, borderRadius: 14, background: C.blueSoft, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <span style={{ width: 14, height: 14, borderRadius: 7, background: C.blue }} />
            </div>
            <div style={{ background: C.card, borderRadius: 15, boxShadow: C.shadowSm, border: "1px solid rgba(36,23,63,0.06)", padding: "10px 24px", flex: 1 }}>
              <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 36, color: C.ink }}>{it.t}</span>
              <span style={{ fontFamily: SANS, fontWeight: 500, fontSize: 21, color: C.sub, marginLeft: 14 }}>{it.d}</span>
            </div>
          </div>
        );
      })}
      {(() => {
        const st = 86;
        const q = seg(local, st, st + 10, E_OUT);
        return (
          <div style={{ marginTop: 8, opacity: q, transform: `translateX(${lerp(46, 0, q)}px)`, display: "inline-flex", alignItems: "center", gap: 12, background: C.blue, borderRadius: 999, padding: "13px 28px", boxShadow: "0 12px 26px rgba(109,59,235,0.32)" }}>
            <span style={{ width: 11, height: 11, borderRadius: 6, background: "#fff" }} />
            <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 27, color: "#fff", letterSpacing: 1 }}>部分房源支持 VR 看房</span>
          </div>
        );
      })()}
    </div>
  );
};

// ---------- on-cam side cards: white cards that sit BEHIND the matted presenter ----------
export const SideCard: React.FC<{ text: string; sub?: string; tag?: string; local: number; start: number; x: number; y: number; w: number; fs?: number }> = ({ text, sub, tag, local, start, x, y, w, fs = 31 }) => {
  const q = seg(local, start, start + 10, E_OUT);
  const s = backLite(seg(local, start, start + 12));
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, opacity: q, transform: `translateY(${lerp(30, 0, q)}px) scale(${lerp(0.96, 1, s)})`, background: "rgba(255,255,255,0.94)", borderRadius: 18, boxShadow: C.shadow, border: "1px solid rgba(36,23,63,0.07)", padding: sub ? "16px 24px" : "16px 24px", display: "flex", alignItems: "center", gap: 18, backdropFilter: "blur(4px)", WebkitBackdropFilter: "blur(4px)" }}>
      {tag ? (
        <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: fs - 1, color: C.blue, minWidth: 40 }}>{tag}</span>
      ) : (
        <span style={{ width: 11, height: 38, borderRadius: 6, background: C.blue, flexShrink: 0, alignSelf: "center" }} />
      )}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: fs, lineHeight: 1.22, color: C.ink, whiteSpace: "nowrap" }}>{text}</div>
        {sub && <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 20, color: C.sub, marginTop: 4, whiteSpace: "nowrap" }}>{sub}</div>}
      </div>
    </div>
  );
};

// ---------- real-Amapi map card with brand pin drops (POI coords projected into the card) ----------
import MAPDATA from "../episode/mappins.json";
const PIN_ORDER = ["链家", "德佑", "21世纪", "中环", "富房"] as const;
// card geometry: map image covers an 1296x690 card at (72,142) from a 1296x972 crop of the 1440x1080 map
const MAP = { x: 72, y: 142, w: 1296, h: 690, imgH: 972, cropY: 141 };
const proj = (px: number, py: number): [number, number] => [
  Math.min(MAP.w - 26, Math.max(26, (px / W) * MAP.w)),
  Math.min(MAP.h - 78, Math.max(24, (py / H) * MAP.imgH - MAP.cropY)),
];

export const PinMapX: React.FC<{ local: number }> = ({ local }) => {
  const groups = PIN_ORDER.map((name) => ({ name, ...(MAPDATA as any)[name] })).filter((g) => g.pts);
  const activeGi = Math.min(groups.length - 1, Math.floor(seg(local, 18, 18 + groups.length * 22) * groups.length));
  return (
    <AbsoluteFill>
      {/* card */}
      <div style={{ position: "absolute", left: MAP.x, top: MAP.y, width: MAP.w, height: MAP.h, borderRadius: 24, overflow: "hidden", boxShadow: C.shadow, border: "1px solid rgba(36,23,63,0.08)", background: "#E9EEF4" }}>
        <AbsoluteFill style={{ transform: `scale(${lerp(1.04, 1, seg(local, 0, 18, E_OUT))})` }}>
          <Img src={staticFile("broll/v2/B04_base.png")} style={{ position: "absolute", left: 0, top: -MAP.cropY, width: MAP.w, height: MAP.imgH }} />
        </AbsoluteFill>
        {/* title plate on the map */}
        <div style={{ position: "absolute", left: 28, top: 24, background: "rgba(255,255,255,0.94)", borderRadius: 14, boxShadow: C.shadowSm, padding: "12px 22px 13px", opacity: seg(local, 4, 14, E_OUT) }}>
          <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 33, color: C.ink, lineHeight: 1.1 }}>成都 · 贝壳平台上的品牌</div>
          <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 18, color: C.sub, marginTop: 3 }}>武侯区门店位置（高德公开 POI · 部分）</div>
        </div>
        {/* pins */}
        {groups.map((g, gi) =>
          (g.pts as number[][]).map((p, pi) => {
            const st = 20 + gi * 22 + pi * 2;
            const q = seg(local, st, st + 8, E_OUT);
            const s = backLite(seg(local, st, st + 10));
            const [cx, cy] = proj(p[0], p[1]);
            return (
              <div key={`${g.name}-${pi}`} style={{ position: "absolute", left: cx - 15, top: cy - 15, width: 30, height: 30, opacity: q, transform: `translateY(${lerp(-70, 0, q)}px) scale(${s})`, filter: "drop-shadow(0 4px 7px rgba(36,23,63,0.35))" }}>
                <div style={{ width: 30, height: 30, borderRadius: 15, background: g.color, border: "3px solid #FFF", boxSizing: "border-box" }} />
                <div style={{ position: "absolute", left: 10, top: 10, width: 10, height: 10, borderRadius: 5, background: "#FFF" }} />
              </div>
            );
          })
        )}
        {/* 德佑 1000+ fact, spoken late, sits in the empty top-right area */}
        <div style={{ position: "absolute", right: 26, top: 30, opacity: seg(local, 150, 162, E_OUT), transform: `scale(${backLite(seg(local, 150, 164))})`, background: "rgba(255,255,255,0.95)", borderRadius: 16, boxShadow: C.shadowSm, padding: "12px 22px 13px", display: "flex", alignItems: "center", gap: 16, transformOrigin: "100% 0" }}>
          <CountNum value="1000+" local={local} start={153} fontSize={58} />
          <span style={{ fontFamily: SANS, fontWeight: 800, fontSize: 24, color: C.ink }}>德佑在成都的门店</span>
        </div>
        {/* map attribution (AGENTS.md §3E: real Amap frames keep the source credit) */}
        <div style={{ position: "absolute", left: 18, bottom: 22, fontFamily: SANS, fontWeight: 500, fontSize: 14, letterSpacing: 0.5, color: "rgba(36,23,63,0.78)", background: "rgba(255,255,255,0.86)", padding: "3px 10px 4px", borderRadius: 6, opacity: seg(local, 8, 16, E_OUT) }}>
          地图数据 © 高德地图（示意，非测绘成果）
        </div>
        {/* legend strip */}
        <div style={{ position: "absolute", left: 0, bottom: 16, width: MAP.w, display: "flex", justifyContent: "center", opacity: seg(local, 8, 16, E_OUT) }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28, background: "rgba(255,255,255,0.94)", borderRadius: 999, padding: "9px 28px", boxShadow: C.shadowSm }}>
            {groups.map((g) => (
              <span key={g.name} style={{ display: "inline-flex", alignItems: "center", gap: 9, fontFamily: SANS, fontWeight: 700, fontSize: 23, color: C.ink }}>
                <span style={{ width: 14, height: 14, borderRadius: 7, background: g.color, display: "inline-block" }} />{g.name}
              </span>
            ))}
          </div>
        </div>
      </div>
      {/* active brand callout, one at a time, above the card */}
      <div style={{ position: "absolute", left: 0, top: MAP.y - 64, width: W, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
        {groups.map((g, gi) => {
          const q = gi === activeGi ? seg(local, 20 + gi * 22, 20 + gi * 22 + 8, E_OUT) * (1 - seg(local, 20 + (gi + 1) * 22 - 6, 20 + (gi + 1) * 22 + 4, E_OUT)) : 0;
          if (q <= 0.01) return null;
          return (
            <div key={g.name} style={{ position: "absolute", opacity: q, transform: `translateY(${lerp(14, 0, q)}px)`, display: "flex", alignItems: "center", gap: 12, background: C.ink, color: "#fff", borderRadius: 999, padding: "9px 26px", boxShadow: C.shadow }}>
              <span style={{ width: 13, height: 13, borderRadius: 7, background: g.color }} />
              <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 29 }}>{g.name}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------- brand logo wall (light): real logos settle into white cards ----------
const Mono: React.FC<{ file: string; h: number; color: string }> = ({ file, h, color }) => {
  const u = `url(${staticFile(file)})`;
  return <div style={{ height: h, width: h * 3.2, background: color, WebkitMaskImage: u, maskImage: u, WebkitMaskSize: "contain", maskSize: "contain", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat", WebkitMaskPosition: "center", maskPosition: "center" }} />;
};
const WALL: { name: string; file?: string; mono?: string; tint?: string }[] = [
  { name: "链家", mono: "broll/v2/lianjia_mono.png", tint: "#00AE66" },
  { name: "德佑", file: "broll/v2/deyou_color.png" },
  { name: "21世纪不动产", file: "broll/v2/c21.png" },
  { name: "中环", file: "broll/v2/zhonghuan_color.png" },
  { name: "富房", mono: "broll/v2/fufang_mono.png", tint: "#C8283C" },
];
export const BrandWallX: React.FC<{ local: number }> = ({ local }) => (
  <AbsoluteFill style={{ background: "linear-gradient(180deg,#FBF8F1 0%,#F4EEFF 100%)" }}>
    <div style={{ position: "absolute", left: 0, width: W, top: 196, textAlign: "center" }}>
      <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 66, color: C.ink, opacity: seg(local, 0, 12, E_OUT), transform: `translateY(${lerp(20, 0, seg(local, 0, 12, E_OUT))}px)` }}>在成都 这些品牌都在贝壳上</div>
      <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 27, color: C.sub, marginTop: 14, opacity: seg(local, 8, 20, E_OUT) }}>平台合作品牌 200+ 成都部分展示</div>
    </div>
    <div style={{ position: "absolute", left: 0, width: W, top: 470, display: "flex", justifyContent: "center", alignItems: "stretch", gap: 34 }}>
      {WALL.map((b, i) => {
        const st = 4 + i * 5;
        const q = seg(local, st, st + 12, E_OUT);
        const s = backLite(seg(local, st, st + 12));
        return (
          <div key={b.name} style={{ width: 232, opacity: q, transform: `perspective(1200px) rotateY(${lerp(-100, 0, q)}deg) translateY(${lerp(40, 0, q)}px) scale(${lerp(0.82, 1, s)})`, background: "#FFF", borderRadius: 22, boxShadow: C.shadow, border: "1px solid rgba(36,23,63,0.07)", padding: "34px 0 30px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 24 }}>
            <div style={{ height: 96, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 22px" }}>
              {b.file ? <Img src={staticFile(b.file)} style={{ maxWidth: 172, maxHeight: 88, objectFit: "contain" }} /> : <Mono file={b.mono!} h={78} color={b.tint!} />}
            </div>
            <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 27, color: C.ink }}>{b.name}</div>
          </div>
        );
      })}
    </div>
  </AbsoluteFill>
);

// ---------- ACN process flow: four nodes, connectors draw on as each role is spoken ----------
const ACN_STEPS = [
  { t: "录入", d: "房源信息上平台" },
  { t: "实勘", d: "VR 全景实勘拍照" },
  { t: "带看", d: "陪客户实地看房" },
  { t: "签约", d: "协助交易签约" },
];
// one geometric icon family for the four ACN roles (house / camera / people / contract)
const StepIcon: React.FC<{ i: number; on: boolean }> = ({ i, on }) => {
  const col = on ? C.blue : "#A99FBF";
  const sw = 5;
  const p = { fill: "none", stroke: col, strokeWidth: sw, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg width={92} height={92} viewBox="0 0 96 96">
      {on && <circle cx="48" cy="48" r="45" fill={C.blueSoft} />}
      {i === 0 && (<g {...p}><path d="M20 48 L48 26 L76 48" /><path d="M29 46 V70 H67 V46" /><path d="M42 70 V56 H54 V70" /></g>)}
      {i === 1 && (<g {...p}><rect x="22" y="34" width="44" height="32" rx="5" /><path d="M22 66 L36 52 L48 62 L60 48 L66 54" /><circle cx="62" cy="40" r="4" /></g>)}
      {i === 2 && (<g {...p}><circle cx="36" cy="38" r="10" /><circle cx="60" cy="38" r="10" /><path d="M18 70 C20 56 30 52 36 52 C42 52 52 56 54 70" /><path d="M50 70 C52 60 58 55 63 56 C69 57 74 62 76 70" /></g>)}
      {i === 3 && (<g {...p}><rect x="26" y="24" width="44" height="48" rx="4" /><path d="M36 38 H60 M36 48 H60 M36 58 H50" /><path d="M56 62 L63 69 L77 53" stroke={on ? C.blue : col} /></g>)}
    </svg>
  );
};
export const AcnFlow: React.FC<{ local: number; steps: string[]; at?: number[] }> = ({ local, steps, at }) => {
  const T = at ?? steps.map((_, i) => 60 + i * 34);
  const active = T.filter((t) => local >= t).length - 1;
  return (
    <AbsoluteFill>
      <ChapterTitle kicker="BEIKE ACN" title="ACN 经纪人合作网络" sub="不同品牌靠一套规则合作 成交按贡献分配" align="center" y={112} />
      <div style={{ position: "absolute", top: 452, left: 0, width: W, display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
        {steps.map((s, i) => {
          const enter = seg(local, 14 + i * 8, 24 + i * 8, E_OUT);
          const actSt = T[i];
          const on = i <= active;
          const meta = ACN_STEPS[i] ?? { t: s, d: "" };
          const connector = i > 0;
          const dq = seg(local, T[i] - 12, T[i] + 4, E_OUT);
          return (
            <React.Fragment key={s}>
              {connector && (
                <div key={`c${i}`} style={{ width: 80, height: 252, display: "flex", alignItems: "center", opacity: enter, flexShrink: 0 }}>
                  <div style={{ position: "relative", width: "100%", height: 4, margin: "0 6px", background: "#E4DCF3", borderRadius: 2 }}>
                    <div style={{ width: `${dq * 100}%`, height: "100%", background: C.blue, borderRadius: 2 }} />
                  </div>
                  <div style={{ marginLeft: -9, width: 0, height: 0, borderTop: "8px solid transparent", borderBottom: "8px solid transparent", borderLeft: `12px solid ${dq > 0.15 ? C.blue : "#E4DCF3"}` }} />
                </div>
              )}
              <div style={{ width: 246, opacity: enter, transform: `perspective(1200px) rotateY(${lerp(-80, 0, enter)}deg) translateY(${lerp(40, 0, enter)}px) scale(${on ? lerp(1, 1.06, seg(local, actSt, actSt + 6) * (1 - seg(local, actSt + 6, actSt + 16))) + 0 : 1})`, flexShrink: 0, filter: on ? `drop-shadow(0 0 ${18 * seg(local, actSt, actSt + 8)}px rgba(255,200,61,0.75))` : "none" }}>
                <div style={{ background: "#FFF", borderRadius: 22, border: `2px solid ${on ? C.blue : "#E4DCF3"}`, boxShadow: on ? "0 20px 46px rgba(109,59,235,0.22)" : C.shadowSm, padding: "26px 0 28px", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 24, color: on ? C.blue : "#A99FBF" }}>{String(i + 1).padStart(2, "0")}</span>
                    <StepIcon i={i} on={on} />
                  </div>
                  <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 46, color: on ? C.ink : "#5E5475" }}>{s}</div>
                  <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 21, color: C.sub, textAlign: "center", padding: "0 14px" }}>{meta.d}</div>
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------- end panel: Beike wordmark, CTA, handles, one brand row (footer source line lives in BrandStrip) ----------
// Holds ~4 s after the sign-off, so the panel itself drifts slowly (taste §7.4 anti-slideshow).
export const EndPanelX: React.FC = () => {
  const f = useCurrentFrame();
  const p = seg(f, 0, 130);
  return (
    <AbsoluteFill style={{ background: "linear-gradient(172deg,#F2ECFF 0%,#FBF8F1 55%,#FFFFFF 100%)", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${1 + 0.03 * p}) translateY(${-8 * p}px)`, transformOrigin: "50% 46%" }}>
        <div style={{ position: "absolute", left: -220, top: -260, width: 720, height: 720, borderRadius: 360, background: "radial-gradient(circle,rgba(109,59,235,0.10) 0%,rgba(109,59,235,0) 70%)" }} />
        <div style={{ position: "absolute", left: 0, width: W, top: 168, textAlign: "center" }}>
          <div style={{ display: "flex", justifyContent: "center", opacity: seg(f, 2, 14, E_OUT), transform: `translateY(${lerp(18, 0, seg(f, 2, 14, E_OUT))}px)` }}>
            <Img src={staticFile("broll/v2/ke.png")} style={{ height: 92, objectFit: "contain" }} />
          </div>
          <div style={{ marginTop: 28, fontFamily: TITLE, fontWeight: 700, fontSize: 76, color: C.ink, opacity: seg(f, 8, 22, E_OUT), letterSpacing: 1 }}>我是小ONE 欢迎关注</div>
          <div style={{ marginTop: 16, fontFamily: SANS, fontWeight: 600, fontSize: 31, color: C.sub, opacity: seg(f, 16, 30, E_OUT) }}>成都租房 二手房 新房 持续分享</div>
        </div>
        <div style={{ position: "absolute", left: 0, width: W, top: 548, display: "flex", justifyContent: "center", gap: 26 }}>
          {["视频号 @贝壳-TV", "抖音 @贝壳TV"].map((t, i) => (
            <div key={t} style={{ opacity: seg(f, 22 + i * 6, 32 + i * 6, E_OUT), transform: `translateY(${lerp(20, 0, seg(f, 22 + i * 6, 32 + i * 6, E_OUT))}px)`, background: i === 0 ? "#FFF" : C.ink, color: i === 0 ? C.ink : "#FFF", border: i === 0 ? "1px solid rgba(36,23,63,0.12)" : "none", borderRadius: 999, padding: "15px 38px", fontFamily: SANS, fontWeight: 800, fontSize: 31, boxShadow: C.shadowSm }}>{t}</div>
          ))}
        </div>
        <div style={{ position: "absolute", left: 0, width: W, top: 752, display: "flex", justifyContent: "center", alignItems: "center", gap: 22, opacity: seg(f, 30, 42, E_OUT) }}>
          {WALL.map((b) => (
            <div key={b.name} style={{ background: "#FFF", borderRadius: 14, boxShadow: C.shadowSm, padding: "10px 20px", height: 78, display: "flex", alignItems: "center" }}>
              {b.file ? <Img src={staticFile(b.file)} style={{ maxWidth: 128, maxHeight: 56, objectFit: "contain" }} /> : <Mono file={b.mono!} h={50} color={b.tint!} />}
            </div>
          ))}
        </div>
        <div style={{ position: "absolute", left: 0, width: W, top: 872, textAlign: "center", fontFamily: SANS, fontWeight: 600, fontSize: 21, color: C.sub, opacity: seg(f, 38, 48, E_OUT) }}>平台经纪品牌（部分）</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
