import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Img, Sequence, staticFile, useCurrentFrame, getInputProps } from "remotion";
import { TITLE, SANS } from "./shared/fonts";
import { PAL } from "./shared/palette";
import { E_OUT, seg as ease } from "./shared/lib";
import TL from "./episode/timeline.json";
import LAY from "./episode/layout.json";
import { BrandStrip } from "./components/BrandStrip";
import { SocialBadge } from "./components/SocialBadge";

type Box = { x: number; y: number; w: number; h: number };
type Seg = { id: string; layout: "question" | "name" | "case" | "data"; f0: number; f1: number; speaker: string; shot: string; video_src?: string; foreground_src?: string; card_id?: string | null; question?: string | null };
type Cap = { text: string; f0: number; f1: number; speaker: string };
type Card = { id?: string; label: string; price_label: string; value: string; unit: string; source: string; collected_on: string; basis: string };

const timeline = TL as {
  fps: number; total: number; width: number; height: number; show: string; topic: string; region: string;
  background: string; background_src?: string; technical_test: boolean; audio?: { src: string } | null;
  studio?: { foreground?: Box; grade?: { brightness?: number; contrast?: number; saturation?: number }; compact_cards?: boolean; background_blur?: number };
  segments: Seg[]; captions: Cap[]; cards: Card[]; checklist: string[];
  guest: { display_name?: string; store?: string; brand?: string };
};
const boxes = (LAY as { boxes: Record<string, Box> }).boxes;
export const TOTAL = timeline.total;
export const FPS = timeline.fps;
export const WIDTH = timeline.width;
export const HEIGHT = timeline.height;
const ENTER = Math.max(1, Math.round((10 / 30) * timeline.fps));

const at = (box: Box): React.CSSProperties => ({ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h });

const Backdrop: React.FC<{ mode: string }> = ({ mode }) => (
  <AbsoluteFill style={{ background: `linear-gradient(180deg, ${PAL.land} 0%, #E4D3C0 58%, #CDB59A 100%)` }}>
    {timeline.background_src ? <Img src={staticFile(timeline.background_src)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: `blur(${Math.min(16, Math.max(0, timeline.studio?.background_blur ?? 0))}px)`, transform: timeline.studio?.background_blur ? "scale(1.02)" : undefined }} /> : null}
    {!timeline.background_src ? <div style={{ position: "absolute", left: 980, top: 70, width: 860, height: 760, background: "#F7F1E8", border: "1px solid rgba(72,60,50,0.18)" }} /> : null}
    {!timeline.background_src ? <div style={{ position: "absolute", left: 1080, top: 110, width: 220, height: 280, background: "rgba(236,206,112,0.35)" }} /> : null}
    {mode !== "live" && !timeline.background_src ? (
      <div style={{ position: "absolute", left: 72, top: 780, width: 980, color: PAL.ink, fontFamily: SANS, fontSize: 22 }}>
        {mode === "virtual" ? "虚拟会客厅占位 · 无参考帧，未做真实机位匹配" : "技术测试底 · 固定机位，无虚拟绕拍"}
      </div>
    ) : null}
  </AbsoluteFill>
);

const GuestBlock: React.FC = () => (
  <div style={{ ...at(boxes.face), background: "rgba(154,70,61,0.16)", border: `2px solid ${PAL.accent}`, display: "flex", alignItems: "flex-end", padding: 18 }}>
    <div style={{ fontFamily: SANS, fontSize: 28, color: PAL.ink, lineHeight: 1.25 }}>
      {timeline.technical_test ? "技术测试" : "嘉宾"}
      <div style={{ fontSize: 18, marginTop: 6 }}>占位 · 非真人</div>
    </div>
  </div>
);

const CardShell: React.FC<{ box: Box; kicker: string; title: string; lines: string[] }> = ({ box, kicker, title, lines }) => {
  const local = useCurrentFrame();
  const shown = ease(local, 0, ENTER, E_OUT);
  const compact = timeline.studio?.compact_cards;
  return (
    <div style={{ ...at(box), ...(compact ? { width: Math.min(box.w, 660), height: "auto", padding: "20px 26px" } : {}), opacity: shown, background: "#FBFAF7", border: "1.5px solid rgba(72,60,50,0.18)", borderRadius: 18, padding: "22px 26px", boxShadow: "0 8px 28px rgba(31,28,23,0.12)" }}>
      <div style={{ fontFamily: SANS, fontSize: 16, letterSpacing: 1, color: "#8A5A12" }}>{kicker}</div>
      <div style={{ fontFamily: TITLE, fontSize: compact ? 32 : 40, color: PAL.ink, marginTop: 8, lineHeight: 1.2 }}>{title}</div>
      {lines.map((line) => (
        <div key={line} style={{ fontFamily: SANS, fontSize: 22, color: PAL.ink, marginTop: 10, lineHeight: 1.35 }}>{line}</div>
      ))}
    </div>
  );
};

const SegmentBody: React.FC<{ seg: Seg; mode: string }> = ({ seg, mode }) => {
  const local = useCurrentFrame();
  const abs = seg.f0 + local;
  const caption = timeline.captions.filter((cap) => cap.f0 <= abs && abs < cap.f1).slice(-1)[0];
  const guest = timeline.guest || {};
  const card = timeline.cards.find((item) => (item.id || item.label) === seg.card_id);
  const foreground = mode === "virtual" ? timeline.studio?.foreground : undefined;
  const grade = mode === "virtual" ? timeline.studio?.grade : undefined;
  return (
    <>
      {(mode === "live" ? seg.video_src : seg.foreground_src) ? <OffthreadVideo
        src={staticFile((mode === "live" ? seg.video_src : seg.foreground_src)!)}
        muted transparent={mode === "virtual"}
        style={{ position: "absolute", left: foreground?.x ?? 1000, top: foreground?.y ?? 100, width: foreground?.w ?? 880, height: foreground?.h ?? 900, objectFit: foreground ? "contain" : "cover", filter: grade ? `brightness(${grade.brightness ?? 1}) contrast(${grade.contrast ?? 1}) saturate(${grade.saturation ?? 1})` : undefined }}
      /> : null}
      {seg.layout === "question" ? (
        <CardShell box={boxes.question} kicker="问题" title={seg.question || timeline.topic || "待填"} lines={[]} />
      ) : null}
      {seg.layout === "name" ? (
        <div style={{ ...at(boxes.namebar), background: PAL.ink, borderRadius: 14, padding: "12px 20px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div style={{ fontFamily: TITLE, fontSize: 32, color: PAL.land }}>{guest.display_name || "待填"}</div>
          <div style={{ fontFamily: SANS, fontSize: 18, color: PAL.gold }}>{guest.store || "待填"} · {guest.brand || "待填"}</div>
        </div>
      ) : null}
      {seg.layout === "case" ? (
        <CardShell box={boxes.case} kicker="房源案例" title={card ? card.label : "待填"} lines={card ? [card.price_label + " " + card.value + card.unit, card.source + " · " + card.collected_on, card.basis] : ["没有允许公开的数据", "不推断价格"]} />
      ) : null}
      {seg.layout === "data" ? (
        <CardShell box={boxes.datascreen} kicker="资料" title={card?.label || timeline.topic} lines={card ? [card.basis, card.source, card.collected_on] : [timeline.technical_test ? "技术测试资料画面" : timeline.region]} />
      ) : null}
      {caption ? (
        <div style={{ ...at(boxes.caption), display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontFamily: SANS, fontSize: 28, color: "#F7F1E8", background: "rgba(31,28,23,0.72)", borderRadius: 999, padding: "8px 22px", maxWidth: "100%", lineHeight: 1.35, textAlign: "center" }}>{caption.text}</span>
        </div>
      ) : null}
    </>
  );
};

export const InterviewLounge: React.FC = () => {
  const props = getInputProps() as { background?: string };
  const mode = props.background || timeline.background || "placeholder";
  return (
    <AbsoluteFill style={{ background: PAL.land, fontFamily: SANS }}>
      <Backdrop mode={mode} />
      {mode === "placeholder" ? <GuestBlock /> : null}
      {timeline.technical_test && mode === "placeholder" ? (
        <div style={{ ...at(boxes.gesture), border: "1px dashed rgba(72,60,50,0.35)", color: PAL.ink, fontSize: 16, padding: 8 }}>手势安全区</div>
      ) : null}
      <div style={{ ...at(boxes.bug), background: PAL.ink, color: PAL.land, borderRadius: 10, display: "flex", alignItems: "center", paddingLeft: 16, fontFamily: TITLE, fontSize: 26 }}>{timeline.show}</div>
      <div style={{ ...at(boxes.region), background: PAL.gold, color: PAL.ink, borderRadius: 999, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>{timeline.region || "待填"}</div>
      {timeline.technical_test ? (
        <div style={{ position: "absolute", left: 720, top: 36, fontFamily: TITLE, fontSize: 28, color: PAL.accent }}>技术测试</div>
      ) : null}
      {timeline.segments.map((seg) => (
        <Sequence key={seg.id} from={seg.f0} durationInFrames={Math.max(1, seg.f1 - seg.f0)}>
          <SegmentBody seg={seg} mode={mode} />
        </Sequence>
      ))}
      {timeline.audio?.src ? <Audio src={staticFile(timeline.audio.src)} /> : null}
      <SocialBadge />
      <BrandStrip />
    </AbsoluteFill>
  );
};
