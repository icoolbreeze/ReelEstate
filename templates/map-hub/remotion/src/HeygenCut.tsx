// HeyGen avatar cut: a 3–5 s on-camera hook (avatar full screen, lip-synced to our audio) BEFORE the opener, then the full map-hub
// episode (MapHubKoubo) unchanged in its own timebase. Hook data: timeline.json `hook` (build_vo.py --script script_v2.json).
import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame } from "remotion";
import TL from "./episode/timeline.json";
import FOOT from "./episode/footage.json";
import { MapHubKoubo, TOTAL } from "./MapHubKoubo";
import { ClipMedia, Footage } from "./components/ScanAnnotate";
import { BrandStrip } from "./components/BrandStrip";
import { SocialBadge } from "./components/SocialBadge";
import { SANS } from "./fonts";
import { E_OUT, lerp, seg } from "./lib";
import { Img } from "remotion";
import { TITLE } from "./fonts";
import DATA from "./episode/listings.json";
import HUB from "./episode/hub.json";

const CHOSEN = (DATA.mid as any[]).find((l) => l.id === DATA.chosenId);
type Hook = { id: string; clip: string; f0: number; f1: number; frames: number; caps: { text: string; f0: number; f1: number }[] };
const HOOK = (TL as unknown as { hook?: Hook }).hook;
export const HOOK_FRAMES = HOOK?.frames ?? 0;
export const HEYGEN_TOTAL = HOOK_FRAMES + TOTAL;
const FO = FOOT as unknown as Record<string, Footage>;

// HG segments: native 4:3 1440x1080 after runbook 7b (heygen_43.py). footage.json w/h = 1440x1080, so ClipMedia/mediaGeom
// place them 1:1 with no crop; a 16:9 1280x720 segment (fallback, no 7b) is still cover-cropped around cx. HG00_alpha must
// be matted from the same HG00 segment (same size).
// Hook overlay presets (v8). Plate + presenter are fixed; only the overlay changes. Back to front:
//   1 HeyGen plate (native 4:3) -> 2 title -> 3 facts + photo cards + preset extras -> 4 presenter alpha (HG00_alpha)
//   -> 5 caption pill -> 6 brand strip (unchanged). Title and cards always sit BEHIND the matted presenter.
// preset: original (default, approved bold look) | minimal | paper | gold | block   (Composition prop `preset`)
// Title spans ~95 % of the width (1368 px). Motion (video-taste section 7): entries bezier(.16,1,.3,1), 10-12 f, staggered;
// title drift 1.00->1.03 over the hook; no overshoot; deterministic.
import { loadFont as loadHookFont } from "@remotion/fonts";
loadHookFont({ family: "HookSerifSC", url: staticFile("fonts/paper/NotoSerifSC-Black.otf"), weight: "900", format: "opentype" });
loadHookFont({ family: "HookSerifSC", url: staticFile("fonts/paper/NotoSerifSC-SemiBold.otf"), weight: "600", format: "opentype" });
loadHookFont({ family: "HookGaramond", url: staticFile("fonts/paper/EBGaramond-VariableFont_wght.ttf"), weight: "400 800", format: "truetype" });
const SERIF = `HookSerifSC, "Noto Serif SC", serif`;
const GARA = `HookGaramond, HookSerifSC, serif`;

export type HookPreset = "original" | "minimal" | "paper" | "gold" | "block";
export const HOOK_PRESETS: HookPreset[] = ["original", "minimal", "paper", "gold", "block"];

type Skin = {
  title: (q: number) => React.CSSProperties;   // per-char style
  titleShadowCopy?: React.CSSProperties;       // optional offset solid copy behind the title (block)
  factInk: string; accent: React.CSSProperties; factFont: string; factBand?: string;
  card: { pad: string; bg: string; border?: string; shadow: string; radius: number; tilt: number[] };
  tag: (label: string) => React.ReactNode;
};

const SKINS: Record<HookPreset, Skin> = {
  // original = the approved bold hook (hook_bold_v1): off-white heavy-sans title, gold rent, 12 px off-white cards, big cards
  original: {
    title: () => ({ fontFamily: TITLE, fontWeight: 700, color: "#FBFAF7", textShadow: "0 6px 24px rgba(38,32,24,0.35)" }),
    factInk: "#FBFAF7", factFont: SANS,
    accent: { color: "#ECCE70" },
    card: { pad: "12px", bg: "#FBFAF7", shadow: "0 18px 40px rgba(38,32,24,0.30), 0 3px 8px rgba(38,32,24,0.18)", radius: 6, tilt: [-3, 3.5] },
    tag: (l) => <span style={{ position: "absolute", left: 24, bottom: 24, padding: "5px 14px 7px", borderRadius: 6, background: "rgba(251,250,247,0.94)", color: "#3A3D42", fontFamily: SANS, fontWeight: 800, fontSize: 30 }}>{l}</span>,
  },
  minimal: {
    title: () => ({ fontFamily: TITLE, fontWeight: 700, color: "#FFFFFF", textShadow: "0 10px 34px rgba(24,18,12,0.55), 0 2px 6px rgba(24,18,12,0.35)" }),
    factInk: "#FFFFFF", factFont: SANS,
    accent: { color: "#FF5A1F" },
    card: { pad: "8px", bg: "#FFFFFF", shadow: "0 26px 54px rgba(24,18,12,0.50), 0 4px 10px rgba(24,18,12,0.25)", radius: 4, tilt: [-2.5, 3] },
    tag: (l) => <span style={{ position: "absolute", left: 18, bottom: 18, padding: "3px 10px 5px", background: "#FFFFFF", color: "#141214", fontFamily: SANS, fontWeight: 800, fontSize: 24, borderRadius: 3 }}>{l}</span>,
  },
  paper: {
    title: () => ({ fontFamily: SERIF, fontWeight: 900, color: "#1F1B16", textShadow: "0 0 18px rgba(251,246,236,0.75), 0 2px 0 rgba(251,246,236,0.6)" }),
    factInk: "#1F1B16", factFont: SERIF,
    accent: { color: "#B5482A" },
    card: { pad: "14px 14px 60px", bg: "#FBF6EC", shadow: "0 18px 36px rgba(48,36,24,0.32), 0 2px 6px rgba(48,36,24,0.2)", radius: 2, tilt: [-4, 3] },
    tag: (l) => <>
      <span style={{ position: "absolute", left: 0, right: 0, bottom: 12, textAlign: "center", fontFamily: SERIF, fontWeight: 600, fontSize: 28, color: "#1F1B16" }}>{l}</span>
      <span style={{ position: "absolute", left: "50%", top: -16, width: 120, height: 34, marginLeft: -60, background: "rgba(232,220,190,0.78)", transform: "rotate(-4deg)", boxShadow: "0 1px 3px rgba(48,36,24,0.18)" }} />
    </>,
  },
  gold: {
    title: () => ({ fontFamily: SERIF, fontWeight: 900, backgroundImage: "linear-gradient(180deg, #EFE8DA 15%, #C9A86A 85%)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", filter: "drop-shadow(0 6px 16px rgba(26,20,10,0.65)) drop-shadow(0 1px 2px rgba(26,20,10,0.6))" }),
    factInk: "#EFE8DA", factFont: SERIF,
    accent: { color: "#C9A86A" },
    card: { pad: "6px", bg: "rgba(20,16,10,0.35)", border: "2px solid #C9A86A", shadow: "0 20px 44px rgba(26,20,10,0.45)", radius: 2, tilt: [-2, 2.5] },
    tag: (l) => <span style={{ position: "absolute", left: 18, bottom: 18, padding: "3px 14px 5px", border: "1.5px solid #C9A86A", borderRadius: 999, background: "rgba(20,16,10,0.55)", color: "#EFE8DA", fontFamily: SERIF, fontWeight: 600, fontSize: 24, letterSpacing: 2 }}>{l}</span>,
  },
  block: {
    title: () => ({ fontFamily: TITLE, fontWeight: 700, color: "transparent", WebkitTextStroke: "3px #F6F3EC" }),
    titleShadowCopy: { color: "#0F6E6A", opacity: 0.92 },
    factInk: "#F6F3EC", factFont: SANS, factBand: "rgba(15,110,106,0.82)",
    accent: { color: "#141214", background: "#E8FF3A", padding: "0 14px 4px", borderRadius: 6 },
    card: { pad: "10px", bg: "#F6F3EC", shadow: "8px 8px 0 #000", radius: 0, tilt: [-2, 2.5] },
    tag: (l) => <span style={{ position: "absolute", left: 10, bottom: 10, padding: "4px 12px 6px", background: "#0F6E6A", color: "#F6F3EC", fontFamily: SANS, fontWeight: 800, fontSize: 24 }}>{l}</span>,
  },
};

const HookShot: React.FC<{ preset: HookPreset }> = ({ preset }) => {
  const f = useCurrentFrame();
  const H = HOOK!;
  const S = SKINS[preset] ?? SKINS.original;
  const fo = FO[H.clip] ?? FO.P1;
  const matte = FO[`${H.clip}_alpha`];
  const ci = H.caps.filter((c) => c.f0 <= f).length - 1;
  const cap = H.caps[Math.max(0, ci)];
  const pop = seg(f, cap.f0, cap.f0 + 5, E_OUT);
  const title: string[] = Array.from(String(CHOSEN.community));
  const TS = Math.min(260, Math.floor(1368 / Math.max(4, title.length)));
  const TOPY = 262;
  const drift = lerp(1, 1.03, seg(f, 0, H.frames));
  const facts = seg(f, 22, 34, E_OUT);
  const extra = seg(f, 16, 28, E_OUT);
  const rooms = (HUB.rooms as any[]).slice(0, 2);
  const FACTY = TOPY + Math.min(260, Math.floor(1368 / Math.max(4, title.length))) + (preset === "gold" ? 74 : 24);
  const big = preset === "original";
  // original: cards ~1.4x (480x312 / 480x330); left card stays above the caption lane (below the facts line; bottom-right corner ~872, above the caption pill), right card clear of the face (x >= 924)
  const cards = big ? [{ x: 36, y: 598, w: 476, h: 300, from: -1, at: 58 }, { x: 924, y: 500, w: 480, h: 330, from: 1, at: 66 }]
    : [{ x: 64, y: Math.max(600, FACTY + 86), w: 340, h: 236, from: -1, at: 58 }, { x: 1036, y: 560, w: 340, h: 236, from: 1, at: 66 }];
  const polaroid = preset === "paper";
  
  const titleRow = (style: (q: number) => React.CSSProperties, dx = 0, dy = 0) => (
    <div style={{ position: "absolute", left: 0, width: 1440, top: TOPY + dy, marginLeft: dx, display: "flex", justifyContent: "center", transform: `scale(${drift})`, transformOrigin: "50% 40%" }}>
      {title.map((c, i) => { const q = seg(f, 4 + i * 2, 16 + i * 2, E_OUT); return (
        <span key={i} style={{ fontSize: TS, lineHeight: 1, display: "inline-block", opacity: q, transform: `translateY(${lerp(60, 0, q)}px)`, ...style(q) }}>{c}</span>); })}
    </div>
  );
  const factY = TOPY + TS + (preset === "gold" ? 74 : 24);
  return (
    <AbsoluteFill>
      <Audio src={staticFile("episode/hook.wav")} />
      <AbsoluteFill><ClipMedia fo={fo} id={H.clip} local={f} inFrame={0} /></AbsoluteFill>
      {/* 2 title (behind presenter) */}
      {S.titleShadowCopy && titleRow(() => ({ fontFamily: TITLE, fontWeight: 700, ...S.titleShadowCopy }), 10, 10)}
      {titleRow(S.title)}
      {/* preset extras (behind presenter) */}
      {preset === "minimal" && <div style={{ position: "absolute", left: 72, top: TOPY - 64, opacity: extra, fontFamily: SANS, fontWeight: 700, fontSize: 26, letterSpacing: 3, color: "#FFFFFF", textShadow: "0 2px 10px rgba(24,18,12,0.5)", display: "flex", alignItems: "center", gap: 16 }}>
        <span>EP07 · 杭州租房</span><span style={{ width: lerp(0, 220, extra), height: 1, background: "rgba(255,255,255,0.85)" }} /></div>}
      {preset === "paper" && <div style={{ position: "absolute", left: 0, width: 1440, top: TOPY - 70, textAlign: "center", opacity: extra, fontFamily: GARA, fontWeight: 600, fontSize: 30, letterSpacing: 10, color: "#1F1B16", textShadow: "0 0 12px rgba(251,246,236,0.8)" }}>
        <span style={{ borderTop: "1.5px solid #1F1B16", borderBottom: "1.5px solid #1F1B16", padding: "4px 18px" }}>ISSUE 07 · HANGZHOU</span></div>}
      {preset === "gold" && <div style={{ position: "absolute", left: 0, width: 1440, top: TOPY + TS + 18, textAlign: "center", opacity: extra, fontFamily: GARA, fontWeight: 600, fontSize: 30, letterSpacing: 9, color: "#E9D9B4", textShadow: "0 2px 10px rgba(26,20,10,0.7)" }}>XIHU CULTURAL SQUARE · RESIDENCE</div>}
      {/* 3a facts line */}
      <div style={{ position: "absolute", left: 72, top: factY, opacity: facts, transform: `translateX(${lerp(-30, 0, facts)}px)`, fontFamily: S.factFont, fontWeight: 800, fontSize: 54, color: S.factInk, fontVariantNumeric: "tabular-nums",
        textShadow: preset === "paper" ? "0 0 14px rgba(251,246,236,0.8)" : preset === "block" ? "none" : preset === "original" ? "0 6px 24px rgba(38,32,24,0.35)" : "0 3px 14px rgba(24,18,12,0.55)",
        background: S.factBand, padding: S.factBand ? "6px 18px 10px" : undefined, borderBottom: preset === "minimal" ? "1px solid rgba(255,255,255,0.85)" : undefined }}>
        <span style={S.accent}>{CHOSEN.rent}</span><span style={{ fontSize: 34, fontWeight: 700 }}> 元/月</span>
        <span style={{ fontSize: 34, fontWeight: 700 }}>{`  ·  ${CHOSEN.layout}  ·  ${CHOSEN.area}㎡`}</span>
      </div>
      {/* 3b photo cards (behind presenter) */}
      {rooms.map((r, i) => { const c = cards[i]; const q = seg(f, c.at, c.at + 10, E_OUT); const rot = S.card.tilt[i] ?? 0; const src = FO[r.clip]?.still ?? r.photo; return (
        <div key={i} style={{ position: "absolute", left: c.x, top: c.y, width: c.w, height: c.h + (polaroid ? 48 : 0), padding: S.card.pad, background: S.card.bg, border: S.card.border, borderRadius: S.card.radius, boxShadow: S.card.shadow, boxSizing: "border-box",
          opacity: q, transform: `translateX(${lerp(c.from * 120, 0, q)}px) rotate(${lerp(rot * 2.2, rot, q)}deg)` }}>
          <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block", borderRadius: preset === "minimal" ? 2 : 0 }} />
          {S.tag(r.label)}
        </div>); })}
      {/* 4 presenter in front */}
      <AbsoluteFill>{matte ? <ClipMedia fo={matte} id={`${H.clip}_alpha`} local={f} inFrame={0} transparent /> : null}</AbsoluteFill>
      {/* 5 caption, 6 brand strip (unchanged) */}
      <div style={{ position: "absolute", left: 0, width: 1440, bottom: 132, textAlign: "center" }}>
        <span style={{ display: "inline-block", padding: "9px 18px 11px", borderRadius: 12, background: "rgba(18,16,14,0.62)", color: "#FFFFFF", fontFamily: SANS, fontWeight: 800, fontSize: 32, lineHeight: 1.25, textAlign: "center", transform: `scale(${lerp(0.92, 1, pop)})`, transformOrigin: "50% 100%", opacity: pop }}>{cap.text}</span>
      </div>
      <BrandStrip dark={0} />
    </AbsoluteFill>
  );
};

export const MapHubHeygen: React.FC<{ preset?: HookPreset }> = ({ preset = "original" }) => (
  <AbsoluteFill>
    {HOOK && <Sequence durationInFrames={HOOK_FRAMES}><HookShot preset={preset} /></Sequence>}
    <Sequence from={HOOK_FRAMES}><MapHubKoubo /></Sequence>
    {/* persistent top-right social badge (handles from the presenter profile) */}
    <SocialBadge />
  </AbsoluteFill>
);
