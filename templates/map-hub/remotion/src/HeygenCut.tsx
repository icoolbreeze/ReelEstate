// HeyGen avatar cut: a 3–5 s on-camera hook (avatar full screen, lip-synced to our audio) BEFORE the opener, then the full map-hub
// episode (MapHubKoubo) unchanged in its own timebase. Hook data: timeline.json `hook` (build_vo.py --script script_v2.json).
import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame } from "remotion";
import TL from "./episode/timeline.json";
import FOOT from "./episode/footage.json";
import { MapHubKoubo, TOTAL } from "./MapHubKoubo";
import { ClipMedia, Footage } from "./components/ScanAnnotate";
import { BrandStrip } from "./components/BrandStrip";
import { SANS } from "./fonts";
import { E_OUT, PAL, lerp, seg } from "./lib";
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

// Hook (v6): the unmatted HeyGen clip itself is the full-bleed background (the host's own room) — no map, no scrim.
// Title/facts/photos park in the side columns BEHIND the avatar matte (they tuck behind the shoulders; face/hands/chest
// stay clear). The existing HG00_alpha webm stays — no new matte; if it is missing, the plain clip is used with no mask.
const HookShot: React.FC = () => {
  const f = useCurrentFrame();
  const H = HOOK!;
  const fo = FO[H.clip] ?? FO.P1;
  const matte = FO[`${H.clip}_alpha`];
  const ci = H.caps.filter((c) => c.f0 <= f).length - 1;
  const cap = H.caps[Math.max(0, ci)];
  const pop = seg(f, cap.f0, cap.f0 + 5, E_OUT);
  const at = (i: number) => H.caps[Math.min(i, H.caps.length - 1)].f0;
  const row = (i: number, d = 0) => seg(f, at(i) + d, at(i) + d + 9, E_OUT);
  const texts: [string, string][] = [["月租", `${CHOSEN.rent}元 · ${CHOSEN.area}㎡`], ["室内", "落地窗 · 人字拼"], ["地铁", "站点 571米"]];
  const imgs = (HUB.rooms as any[]).slice(0, 2).map((r) => FO[r.clip]?.still ?? r.photo);
  return (
    <AbsoluteFill>
      <Audio src={staticFile("episode/hook.wav")} />
      {/* layer 1 (back): the unmatted HeyGen clip itself, full-bleed — the host's own room (no map, no scrim) */}
      <AbsoluteFill>
        <ClipMedia fo={fo} id={H.clip} local={f} inFrame={0} />
      </AbsoluteFill>
      {/* layer 2 (mid, behind matte): community title + three fact rows, upper left (ends by x=520, above y=640,
          so they stay off the face and torso) */}
      <div style={{ position: "absolute", left: 64, top: 138, width: 456, fontFamily: SANS, color: "#FFFFFF" }}>
        <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 52, textShadow: "0 2px 10px rgba(0,0,0,0.5)", opacity: row(0, -8), transform: `translateY(${lerp(16, 0, row(0, -8))}px)` }}>{CHOSEN.community}</div>
        {texts.map(([k, v], i) => { const q = row(i); return (
          <div key={k} style={{ display: "flex", alignItems: "baseline", gap: 16, marginTop: 26, paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.22)", opacity: q, transform: `translateY(${lerp(18, 0, q)}px)` }}>
            <span style={{ width: 56, fontSize: 22, fontWeight: 600, color: PAL.gold }}>{k}</span><span style={{ fontSize: 32, fontWeight: 700, textShadow: "0 2px 8px rgba(0,0,0,0.45)" }}>{v}</span>
          </div>); })}
      </div>
      {/* layer 2 (mid, behind matte): two room photos, right column (starts at x=1040) */}
      <div style={{ position: "absolute", left: 1040, top: 190, width: 330 }}>
        {imgs.map((src, i) => { const q = row(i, 3 + i * 3); return (
          <div key={i} style={{ marginBottom: 22, height: 240, borderRadius: 14, overflow: "hidden", boxShadow: "0 10px 24px rgba(20,14,8,0.35)", opacity: q, transform: `translateX(${lerp(40, 0, q)}px)` }}>
            <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </div>); })}
      </div>
      {/* layer 3 (front): avatar alpha clip, unchanged (existing HG00_alpha webm); if it is missing, the plain
          unmatted clip with no extra mask */}
      <AbsoluteFill>
        {matte ? <ClipMedia fo={matte} id={`${H.clip}_alpha`} local={f} inFrame={0} transparent />
          : <ClipMedia fo={fo} id={H.clip} local={f} inFrame={0} />}
      </AbsoluteFill>
      {/* layer 4: spoken caption — one pill in the caption lane above the brand strip; full width, centred,
          never in the fact column (clear of the fact rows, the face, and the brand strip) */}
      <div style={{ position: "absolute", left: 0, width: 1440, bottom: 132, textAlign: "center" }}>
        <span style={{ display: "inline-block", padding: "9px 18px 11px", borderRadius: 12, background: "rgba(18,16,14,0.62)", color: "#FFFFFF", fontFamily: SANS, fontWeight: 800, fontSize: 32, lineHeight: 1.25, textAlign: "center", transform: `scale(${lerp(0.92, 1, pop)})`, transformOrigin: "50% 100%", opacity: pop }}>{cap.text}</span>
      </div>
      {/* layer 5: brand strip, light variant to match the bright room */}
      <BrandStrip dark={0} />
    </AbsoluteFill>
  );
};

export const MapHubHeygen: React.FC = () => (
  <AbsoluteFill>
    {HOOK && <Sequence durationInFrames={HOOK_FRAMES}><HookShot /></Sequence>}
    <Sequence from={HOOK_FRAMES}><MapHubKoubo /></Sequence>
  </AbsoluteFill>
);
