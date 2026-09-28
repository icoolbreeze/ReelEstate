import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, staticFile, useVideoConfig } from "remotion";
import type { Project } from "../types";
import { Captions } from "./Captions";
import { DisclaimerBadge } from "./DisclaimerBadge";
import { InfoBar, type InfoField } from "./InfoBar";
import { InfoCard } from "./InfoCard";
import { PresenterFrame } from "./PresenterFrame";
import { BG, FONT_FAMILY, MUTED } from "./theme";
import { buildTimeline, type TimelineItem } from "./timeline";
import { ShotVideo } from "../shots/ShotVideo";

const isVideo = (f: string) => /\.(mp4|mov|webm|mkv)$/i.test(f);

const Backdrop: React.FC<{ item: TimelineItem; accent: string }> = ({ item, accent }) => {
  const { width } = useVideoConfig();
  const { broll } = item.seg;
  if (broll) {
    const style: React.CSSProperties = { width: "100%", height: "100%", objectFit: "cover" };
    return (
      <AbsoluteFill>
        {isVideo(broll) ? <OffthreadVideo src={staticFile(broll)} muted style={style} /> : <Img src={staticFile(broll)} style={style} />}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, ${BG} 0%, #E7ECF6 60%, ${accent}1F 100%)`,
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT_FAMILY,
        color: MUTED,
        fontSize: width * 0.016,
      }}
    >
      {item.seg.card ? null : "实拍 / 户型图 / Canva 卡片占位"}
    </AbsoluteFill>
  );
};

const SegmentScene: React.FC<{ item: TimelineItem; accent: string }> = ({ item, accent }) => {
  const { seg } = item;
  const full = seg.presenter === "fullscreen";
  const hasClip = typeof seg.presenter_clip === "string" && seg.presenter_clip.length > 0;
  // Fullscreen with a clip: person fills the frame, card on the right.
  // Fullscreen without a clip: backdrop, card centered.
  // PiP: backdrop always; pip-left card on the right, pip-right card on the left.
  const cardSide: "left" | "right" | "center" = full
    ? hasClip
      ? "right"
      : "center"
    : seg.presenter === "pip-left"
      ? "right"
      : "left";
  return (
    <AbsoluteFill>
      {full && hasClip ? (
        <PresenterFrame mode="fullscreen" clip={seg.presenter_clip} clipStart={seg.clip_start} accent={accent} />
      ) : (
        <Backdrop item={item} accent={accent} />
      )}
      {seg.card ? <InfoCard card={seg.card} accent={accent} side={cardSide} /> : null}
      {!full && hasClip ? (
        <PresenterFrame mode={seg.presenter} clip={seg.presenter_clip} clipStart={seg.clip_start} accent={accent} />
      ) : null}
      <Captions text={seg.text} />
      {item.audio?.file ? <Audio src={staticFile(item.audio.file)} /> : null}
    </AbsoluteFill>
  );
};

type Props = { project: Project; accent: string; fields: InfoField[] };

/** Shared layout used by every category composition. Categories customise accent + InfoBar fields. */
export const BaseLayout: React.FC<Props> = ({ project, accent, fields }) => {
  const { fps } = useVideoConfig();
  const timeline = buildTimeline(project, fps);
  // v5: when pipeline/render.py injects shots.json, render the styled shot timeline instead.
  if (project.shots?.shots?.length) return <ShotVideo project={project} fields={fields} />;
  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {timeline.map((item) => (
        <Sequence key={item.seg.id} from={item.from} durationInFrames={item.duration} name={item.seg.id}>
          <SegmentScene item={item} accent={accent} />
          <DisclaimerBadge labels={item.seg.visual_label ? [item.seg.visual_label] : []} />
        </Sequence>
      ))}
      <InfoBar fields={fields} accent={accent} />
      <GlobalBadges project={project} />
    </AbsoluteFill>
  );
};

const GlobalBadges: React.FC<{ project: Project }> = ({ project }) => {
  const { width } = useVideoConfig();
  const labels = [
    project.is_example ? "示例数据" : "",
    project.ai_voice ? "含AI合成配音" : "",
    project.ad_disclosure ? "广告" : "",
  ].filter(Boolean);
  if (!labels.length) return null;
  return (
    <div style={{ position: "absolute", top: width * 0.02, left: width * 0.02 }}>
      <DisclaimerBadgeInline labels={labels} />
    </div>
  );
};

const DisclaimerBadgeInline: React.FC<{ labels: string[] }> = ({ labels }) => {
  const { width } = useVideoConfig();
  return (
    <div style={{ display: "flex", gap: 8 }}>
      {labels.map((l) => (
        <span
          key={l}
          style={{
            fontFamily: FONT_FAMILY,
            fontSize: width * (width < 1200 ? 0.022 : 0.013),
            color: "#fff",
            background: "rgba(200,40,40,0.75)",
            borderRadius: 6,
            padding: "2px 10px",
          }}
        >
          {l}
        </span>
      ))}
    </div>
  );
};
