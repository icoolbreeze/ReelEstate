// @贝壳-TV knowledge 口播 (series "knowledge", projects/knowledge)
// Pro Redesign: Layered Cinematic & Behind-the-Presenter Motion System
// Layer 1: HeyGen Room Video (Plate)
// Layer 2: Graphic Cards & Title Typography (Behind Presenter)
// Layer 3: Matted Foreground Presenter (HG00_alpha.webm)
// Layer 4: Centered Spoken Captions & BrandStrip
import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame } from "remotion";
import { SANS } from "./fonts";
import TL from "./episode/timeline.json";
import FOOT from "./episode/footage.json";
import EP from "./episode/episode.json";
import { ClipMedia, Footage } from "./components/ScanAnnotate";
import { BrandStrip } from "./components/BrandStrip";
import { SocialBadge } from "./components/SocialBadge";
import { EndPanelX } from "./components/MotionV3";
import {
  AcnBlueprintShowcase,
  ChengduBrandsShowcase,
  HookTitleBehind,
  InspectionHudBehind,
  OutroMissionBehind,
  PlatformShowcase,
  StudioCanvas,
  TrustShieldBehind,
} from "./components/MotionPro";
import { E_OUT, lerp, seg } from "./lib";

// captions never show punctuation: punctuation -> space, collapse
const noPunct = (t: string) =>
  t.replace(/[，。、！？；：,.!?;:“”"'‘’（）()《》〈〉【】\[\]—…·～~-]/g, " ").replace(/\s+/g, " ").trim();

type Cap = { text: string; f0: number; f1: number };
type Broll = { ref: string; clip: string; desc: string; f0: number; f1: number };
type Card = { value: string; sub: string };
type Line = {
  id: string; n: number; type: "oncam" | "voiceover"; name: string; text: string;
  f0: number; f1: number; v0: number; v1: number; caps: Cap[]; audio: string;
  clip?: string; onCam?: string; broll?: Broll[]; cards?: Card[]; process?: string[]; end?: boolean;
};

const LINES = TL.lines as unknown as Line[];
export const TOTAL = TL.total as number;
const FO = FOOT as unknown as Record<string, Footage>;
const EPI = EP as any;
void EPI;

const pendingFo = (label: string): Footage => ({ kind: "pending", status: "pending", label, purpose: label });
const localCaps = (line: Line): Cap[] =>
  line.caps.map((c) => ({ text: c.text, f0: c.f0 - line.v0, f1: c.f1 - line.v0 }));

// ---------- slow camera drift: continuous push + pan channel ----------
const Drift: React.FC<{ local: number; span: number; amount?: number; pan?: number; children: React.ReactNode }> = ({
  local, span, amount = 0.045, pan = 12, children
}) => {
  const p = seg(local, 0, Math.max(1, span));
  return (
    <AbsoluteFill style={{ transform: `scale(${1 + amount * p}) translateY(${-pan * p}px)`, transformOrigin: "50% 48%" }}>
      {children}
    </AbsoluteFill>
  );
};

// ---------- spoken caption: elegant pill, ink text, centred above brand strip ----------
const Caption: React.FC<{ caps: Cap[]; top?: number; hold?: number }> = ({ caps, top, hold = 8 }) => {
  const f = useCurrentFrame();
  if (!caps.length) return null;
  const active = caps.filter((c) => c.f0 <= f && f <= c.f1 + hold).pop();
  if (!active) return null;
  const pop = seg(f, active.f0, active.f0 + 5, E_OUT);

  return (
    <div style={{ position: "absolute", left: 0, width: 1440, ...(top != null ? { top } : { bottom: 122 }), textAlign: "center", pointerEvents: "none", zIndex: 60 }}>
      <span style={{
        display: "inline-block",
        maxWidth: 1060,
        padding: "10px 28px 12px",
        borderRadius: 999,
        background: "rgba(15, 23, 42, 0.82)",
        backdropFilter: "blur(16px)",
        color: "#FFFFFF",
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: 34,
        lineHeight: 1.25,
        textAlign: "center",
        boxShadow: "0 14px 36px rgba(0, 0, 0, 0.45)",
        border: "1px solid rgba(255, 255, 255, 0.16)",
        transform: `scale(${lerp(0.94, 1, pop)})`,
        transformOrigin: "50% 100%",
        opacity: pop,
        letterSpacing: 0.8
      }}>
        {noPunct(active.text)}
      </span>
    </div>
  );
};

// ---------- On-Cam (HeyGen) Segment with BEHIND-THE-PRESENTER Layering ----------
const OnCamShot: React.FC<{ line: Line; first: boolean }> = ({ line, first }) => {
  const f = useCurrentFrame();
  const fo = FO[line.clip ?? ""] ?? pendingFo(`HeyGen 段待生成 ${line.clip}`);
  const matte = FO[`${line.clip}_alpha`];
  const speechEnd = line.f1 - line.v0;

  return (
    <AbsoluteFill>
      <Drift local={f} span={line.v1 - line.v0}>
        {/* Layer 1: Background HeyGen Room Scene */}
        <ClipMedia fo={fo} id={line.clip ?? line.id} local={f} inFrame={0} />

        {/* Layer 2: BEHIND THE PRESENTER GRAPHICS & CARDS */}
        {line.id === "S01" && <HookTitleBehind local={f} />}
        {line.id === "S02" && <InspectionHudBehind local={f} />}
        {line.id === "S06" && <TrustShieldBehind local={f} />}
        {line.id === "S07" && <OutroMissionBehind local={f} />}

        {/* Layer 3: FOREGROUND MATTED PRESENTER */}
        {matte && (
          <AbsoluteFill>
            <ClipMedia fo={matte} id={`${line.clip}_alpha`} local={f} inFrame={0} transparent />
          </AbsoluteFill>
        )}
      </Drift>

      {/* Outro End Panel on speech end */}
      {line.end && (
        <Sequence from={speechEnd} durationInFrames={Math.max(1, line.v1 - line.f1)}>
          <EndPanelX />
        </Sequence>
      )}

      {!(line.end && f >= speechEnd) && <Caption caps={localCaps(line)} />}
      <BrandStrip dark={0} />
    </AbsoluteFill>
  );
};

// ---------- Voiceover (B-roll) Segment ----------
const VoShot: React.FC<{ line: Line }> = ({ line }) => {
  const f = useCurrentFrame();
  const span = line.v1 - line.v0;

  if (line.id === "S03") {
    return (
      <AbsoluteFill>
        <Drift local={f} span={span} amount={0.035} pan={10}>
          <PlatformShowcase local={f} />
        </Drift>
        <Caption caps={localCaps(line)} />
        <BrandStrip dark={0} />
      </AbsoluteFill>
    );
  }

  if (line.id === "S04") {
    return (
      <AbsoluteFill>
        <Drift local={f} span={span} amount={0.03} pan={8}>
          <ChengduBrandsShowcase local={f} />
        </Drift>
        <Caption caps={localCaps(line)} />
        <BrandStrip dark={0} />
      </AbsoluteFill>
    );
  }

  if (line.process) {
    return (
      <AbsoluteFill>
        <Drift local={f} span={span} amount={0.035} pan={10}>
          <AcnBlueprintShowcase local={f} />
        </Drift>
        <Caption caps={localCaps(line)} />
        <BrandStrip dark={0} />
      </AbsoluteFill>
    );
  }

  // fallback
  const items = line.broll ?? [];
  return (
    <AbsoluteFill>
      <Drift local={f} span={span} amount={0.035} pan={10}>
        <StudioCanvas />
        {items.map((b) => {
          const fo = FO[b.clip] ?? pendingFo(b.desc);
          const start = b.f0 - line.v0;
          return (
            <Sequence key={b.clip} from={start} durationInFrames={Math.max(1, b.f1 - b.f0)}>
              <ClipMedia fo={fo} id={b.clip} local={Math.max(0, f - start)} inFrame={0} />
            </Sequence>
          );
        })}
      </Drift>
      <Caption caps={localCaps(line)} />
      <BrandStrip dark={0} />
    </AbsoluteFill>
  );
};

export const KnowledgeKoubo: React.FC = () => {
  const firstOnCam = LINES.find((l) => l.type === "oncam")?.id;
  return (
    <AbsoluteFill style={{ background: "#F8FAFC" }}>
      {LINES.map((l) => (
        <Sequence key={l.id} from={l.v0} durationInFrames={Math.max(1, l.v1 - l.v0)}>
          {l.type === "oncam" ? <OnCamShot line={l} first={l.id === firstOnCam} /> : <VoShot line={l} />}
        </Sequence>
      ))}
      {LINES.map((l) => (
        <Sequence key={`${l.id}-audio`} from={l.f0} durationInFrames={Math.max(1, l.f1 - l.f0)}>
          <Audio src={staticFile(l.audio)} />
        </Sequence>
      ))}
      <SocialBadge />
    </AbsoluteFill>
  );
};
