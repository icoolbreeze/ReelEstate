// Focused opening: one listing title, a clear price, and one room preview.
// Uses the episode's original plate, matte, narration and entrance cue frames.
import React from "react";
import { AbsoluteFill, Audio, Img, Loop, Sequence, staticFile, useCurrentFrame } from "remotion";
import { PRESENTER_PH, phLoopLen } from "../MapHubKoubo";
import { ClipMedia, Footage } from "./ScanAnnotate";
import { BrandStrip } from "./BrandStrip";
import { TITLE, SANS, NUM } from "../fonts";
import { E_OUT, PAL, lerp, seg } from "../lib";
import TL from "../episode/timeline.json";
import FOOT from "../episode/footage.json";
import HUB from "../episode/hub.json";
import DATA from "../episode/listings.json";

type Hook = { clip: string; frames: number; caps: { text: string; f0: number; f1: number }[] };
const H = (TL as unknown as { hook: Hook }).hook;
const FO = FOOT as unknown as Record<string, Footage>;
const CHOSEN = (DATA.mid as any[]).find((r) => r.id === DATA.chosenId);

export const ListingHook: React.FC = () => {
  const f = useCurrentFrame();
  const plate = FO[H.clip] ?? FO.P1;
  const matte = FO[H.clip + "_alpha"];
  const loop = matte ? Math.min(phLoopLen(plate), phLoopLen(matte)) : phLoopLen(plate);
  const local = PRESENTER_PH ? f % loop : f;
  const cap = H.caps.filter((c) => c.f0 <= f).pop() ?? H.caps[0];
  const room = HUB.rooms[0] as { clip?: string; photo: string; label: string } | undefined;
  const photo = room ? FO[room.clip ?? ""]?.still ?? room.photo : undefined;
  const entry = (at: number, dx = 0, dy = 16): React.CSSProperties => {
    const p = seg(f, at, at + 12, E_OUT);
    return { opacity: p, transform: "translate3d(" + lerp(dx, 0, p) + "px," + lerp(dy, 0, p) + "px,0)" };
  };
  const media = (fo: Footage, transparent = false) => (
    <ClipMedia fo={fo} id={H.clip + (transparent ? "_alpha" : "")} local={local} inFrame={0} transparent={transparent} sceneRole={transparent ? "foreground" : "world"} />
  );
  return (
    <AbsoluteFill>
      <Audio src={staticFile("episode/hook.wav")} />
      {[2, 44, 96, 138, 150, 172].map((at, i) => (
        <Sequence key={i} from={at + 4} durationInFrames={6} layout="none">
          <Audio src={staticFile("sfx/pop_soft.wav")} volume={0.07} />
        </Sequence>
      ))}
      <AbsoluteFill>{PRESENTER_PH ? <Loop durationInFrames={loop}>{media(plate)}</Loop> : media(plate)}</AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(24,21,18,0.90) 0%, rgba(24,21,18,0.72) 22%, rgba(24,21,18,0.06) 54%, rgba(24,21,18,0) 100%)" }} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(24,21,18,0.50) 0%, rgba(24,21,18,0) 34%)" }} />

      <div data-harmony-foreground="title" style={{ position: "absolute", left: 72, top: 100, color: PAL.card, ...entry(2, 0, -14) }}>
        <div style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 74, lineHeight: 1.15 }}>{CHOSEN.community}</div>
      </div>

      <div style={{ position: "absolute", left: 72, top: 342, color: PAL.card }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, ...entry(172, -18, 0) }}>
          <span style={{ fontFamily: NUM, fontWeight: 700, fontStyle: "italic", fontSize: 120, lineHeight: 1.05, color: PAL.gold }}>{CHOSEN.rent}</span>
          <span style={{ fontFamily: SANS, fontWeight: 600, fontSize: 28 }}>元/月</span>
        </div>
        <div style={{ marginTop: 18, fontFamily: SANS, fontWeight: 700, fontSize: 36, lineHeight: 1.25, ...entry(150, -16, 0) }}>{CHOSEN.layout}</div>
        {(HUB as any).hookFitment && <div style={{ marginTop: 12, fontFamily: SANS, fontWeight: 500, fontSize: 28, color: "#E8E1D7", ...entry(138, -16, 0) }}>{(HUB as any).hookFitment}</div>}
      </div>

      {photo && <div style={{ position: "absolute", left: 72, top: 652, width: 280, height: 186, padding: 6, boxSizing: "border-box", borderRadius: 10, background: PAL.card, boxShadow: "0 12px 26px rgba(24,21,18,0.20)", ...entry(44, -22, 0) }}>
        <Img src={staticFile(photo)} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: 5 }} />
        <span style={{ position: "absolute", left: 14, bottom: 14, padding: "3px 10px", borderRadius: 5, fontFamily: SANS, fontWeight: 700, fontSize: 20, color: PAL.ink, background: PAL.card }}>{room!.label}</span>
      </div>}
      {(HUB as any).hookFloorplan && <div style={{ position: "absolute", right: 72, top: 544, width: 252, height: 290, ...entry(96, 22, 0) }}>
        <Img src={staticFile((HUB as any).hookFloorplan)} style={{ width: "100%", height: "100%", objectFit: "contain", display: "block", filter: "drop-shadow(0 8px 18px rgba(24,21,18,0.25))" }} />
        <span style={{ position: "absolute", left: 8, bottom: 8, padding: "3px 8px", borderRadius: 5, fontFamily: SANS, fontWeight: 600, fontSize: 18, color: PAL.ink, background: PAL.card }}>户型图</span>
      </div>}

      {matte && <AbsoluteFill>{PRESENTER_PH ? <Loop durationInFrames={loop}>{media(matte, true)}</Loop> : media(matte, true)}</AbsoluteFill>}
      {cap && <div style={{ position: "absolute", left: 0, width: 1440, bottom: 118, textAlign: "center" }}>
        <span style={{ display: "inline-block", padding: "9px 18px 11px", borderRadius: 12, background: "rgba(18,16,14,0.62)", color: PAL.card, fontFamily: SANS, fontWeight: 800, fontSize: 32, lineHeight: 1.25 }}>{cap.text}</span>
      </div>}
      <BrandStrip dark={0} />
    </AbsoluteFill>
  );
};
