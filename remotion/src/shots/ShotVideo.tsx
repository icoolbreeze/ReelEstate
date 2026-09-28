import React from "react";
import { AbsoluteFill, Audio, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { EFFECTS, resolveEffects, type EffectId, type ResolvedEffects } from "../effects";
import type { InfoField } from "../shared/InfoBar";
import { buildTimeline } from "../shared/timeline";
import { ensureFonts } from "../styles/fonts";
import { getStyle } from "../styles";
import type { StyleTokens } from "../styles/types";
import type { Project, Shot } from "../types";
import { DataNumber } from "./DataNumber";
import { FloorplanLocator } from "./FloorplanLocator";
import { ListingWall } from "./ListingWall";
import { LocationLabel } from "./LocationLabel";
import { MapReveal } from "./MapReveal";
import { Media } from "./Media";
import { ComplianceStrip, OutroCTA, ShotBadge, SourceTag } from "./Overlays";
import { RoomCard } from "./RoomCard";
import { SpecCard } from "./SpecCard";
import { StyleCaptions } from "./StyleCaptions";
import { StylePresenter } from "./StylePresenter";
import { H, W, src } from "./util";

ensureFonts();

export type ShotItem = { shot: Shot; from: number; duration: number; segFrom: number; segText: string; speechFrames: number };

/** Lay shots onto the narration timeline: each segment's duration is split across its shots by weight. */
export const buildShotItems = (project: Project, fps: number): ShotItem[] => {
  const shots = project.shots?.shots ?? [];
  const items: ShotItem[] = [];
  for (const seg of buildTimeline(project, fps)) {
    let list = shots.filter((s) => s.segment === seg.seg.id);
    if (!list.length) list = [{ id: `auto-${seg.seg.id}`, segment: seg.seg.id, type: "presenter", presenter: seg.seg.presenter }];
    const total = list.reduce((a, s) => a + (s.weight ?? 1), 0);
    let acc = 0;
    let prev = 0;
    const speech = seg.audio?.duration ? Math.round(seg.audio.duration * fps) : seg.duration - 6;
    list.forEach((s, i) => {
      acc += s.weight ?? 1;
      const end = i === list.length - 1 ? seg.duration : Math.round((acc / total) * seg.duration);
      items.push({ shot: s, from: seg.from + prev, duration: Math.max(1, end - prev), segFrom: seg.from, segText: seg.seg.text, speechFrames: speech });
      prev = end;
    });
  }
  return items;
};

/** Curated effect layer for one shot (see rules/effects/, effects.json). */
const EffectLayer: React.FC<{ id?: EffectId; it: ShotItem; project: Project; st: StyleTokens }> = ({ id, it, project, st }) => {
  const e = id ? EFFECTS[id] : undefined;
  if (!e || e.kind !== "shot") return null;
  const C = e.component;
  return <C st={st} project={project} shot={it.shot} duration={it.duration} />;
};

const TransitionLayer: React.FC<{ id?: EffectId; it: ShotItem; st: StyleTokens }> = ({ id, it, st }) => {
  const e = id ? EFFECTS[id] : undefined;
  if (!e || e.kind !== "transition") return null;
  const C = e.component;
  return <C st={st} duration={it.duration} />;
};

const ShotScene: React.FC<{ it: ShotItem; project: Project; st: StyleTokens; fx: ResolvedEffects }> = ({ it, project, st, fx }) => {
  const f = useCurrentFrame();
  const { shot } = it;
  const effectId = fx.shot.get(shot.id);
  const entry = effectId ? EFFECTS[effectId] : undefined;
  const replaces = entry && entry.kind === "shot" ? entry.replaces : "none";
  const clip = project.presenter_clip;
  const media = shot.media ? project.media?.[shot.media] : undefined;
  const fullPresenter = shot.presenter === "fullscreen" || shot.type === "presenter" || shot.type === "outro";
  const pip = shot.presenter === "pip-left" || shot.presenter === "pip-right" ? shot.presenter : undefined;
  const rooms = project.shots?.floorplan?.rooms ?? [];
  const showLocator = Boolean(shot.locator && rooms.length);
  const labels: string[] = [];
  if (media?.ai) labels.push("AI生成");
  let tag = media?.source_tag;
  if (shot.type === "map" && project.map) tag = project.media?.[project.map.image]?.source_tag ?? "素材来源：地图服务商";

  const background = (() => {
    if (shot.type === "wall" && project.wall) return <ListingWall wall={project.wall} st={st} />;
    if (shot.type === "map" && project.map) return <MapReveal image={project.map.image} attribution={project.map.attribution} st={st} showMarker={!shot.location} />;
    if (fullPresenter && clip) return <StylePresenter clip={clip} mode="fullscreen" st={st} startFrom={it.from} />;
    if (shot.media) {
      const dim = shot.type === "spec" ? 0.42 : shot.type === "number" ? 0.55 : 0;
      return <Media file={shot.media} st={st} push={shot.push} dim={dim} />;
    }
    return <AbsoluteFill style={{ backgroundColor: st.dark }} />;
  })();

  const capLeft = showLocator ? 520 : 60;
  const capRight = pip === "pip-right" ? W - st.pip.margin - st.pip.w - 20 : 1380;
  const capL = pip === "pip-left" ? Math.max(capLeft, st.pip.margin + st.pip.w + 20) : capLeft;
  const capBottom = shot.type === "wall" ? st.caption.bottom + 120 : undefined;

  return (
    <AbsoluteFill>
      {background}
      {shot.type === "spec" && !shot.media && fullPresenter ? <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(0,0,0,.55), rgba(0,0,0,0) 70%)" }} /> : null}
      {shot.type === "spec" && shot.media ? <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(0,0,0,.35), rgba(0,0,0,0) 75%)" }} /> : null}
      {shot.room ? <RoomCard room={shot.room} st={st} /> : null}
      {shot.location && replaces !== "location" ? <LocationLabel loc={shot.location} st={st} /> : null}
      {shot.spec && replaces !== "spec" ? <SpecCard spec={shot.spec} st={st} /> : null}
      {shot.number && replaces !== "number" ? <DataNumber num={shot.number} st={st} /> : null}
      {shot.type === "outro" && replaces !== "outro" ? <OutroCTA cta={shot.cta ?? "点击下方组件 预约看房"} agency={project.agency.full_name} st={st} frame={f} /> : null}
      {showLocator ? <FloorplanLocator rooms={rooms} current={shot.locator} st={st} schematic={project.shots?.floorplan?.schematic} /> : null}
      <EffectLayer id={effectId} it={it} project={project} st={st} />
      {pip && clip ? <StylePresenter clip={clip} mode={pip} st={st} startFrom={it.from} /> : null}
      {tag ? <SourceTag text={tag} st={st} /> : null}
      <ShotBadge labels={labels} st={st} />
      {!(shot.type === "wall" && f > it.duration * 0.55) ? (
        <Sequence from={it.segFrom - it.from} layout="none">
          <StyleCaptions text={it.segText} st={st} speechFrames={it.speechFrames} left={capL} right={capRight} bottom={capBottom} />
        </Sequence>
      ) : null}
      <TransitionLayer id={fx.transitionIn.get(shot.id)} it={it} st={st} />
    </AbsoluteFill>
  );
};

/** shots.json-driven renderer shared by every category (Rental / Resale / NewHome) and every style preset. */
export const ShotVideo: React.FC<{ project: Project; fields: InfoField[] }> = ({ project, fields }) => {
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const st = getStyle(project.style ?? project.shots?.style);
  const items = buildShotItems(project, fps);
  const fx = resolveEffects(items.map((i) => i.shot), project.effects);
  const tl = buildTimeline(project, fps);
  const scale = Math.min(width / W, height / H);
  const badges = [project.is_example ? "示例数据" : "", project.ai_voice ? "含AI合成配音" : "", project.ad_disclosure ? "广告" : ""].filter(Boolean);
  const sfx = project.sfx ?? {};
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <div style={{ position: "absolute", width: W, height: H, left: (width - W * scale) / 2, top: (height - H * scale) / 2, transform: `scale(${scale})`, transformOrigin: "top left", overflow: "hidden" }}>
        {items.map((it) => (
          <Sequence key={it.shot.id} from={it.from} durationInFrames={it.duration} name={`${it.shot.id} ${it.shot.type}`}>
            <ShotScene it={it} project={project} st={st} fx={fx} />
          </Sequence>
        ))}
        <ComplianceStrip fields={fields} badges={badges} st={st} />
      </div>
      {tl.map((seg) =>
        seg.audio?.file ? (
          <Sequence key={`vo-${seg.seg.id}`} from={seg.from} durationInFrames={seg.duration} layout="none">
            <Audio src={src(seg.audio.file)} />
          </Sequence>
        ) : null,
      )}
      {items.map((it) => {
        const kind = it.shot.type === "presenter" || it.shot.type === "outro" ? null : sfx.whoosh;
        return kind ? (
          <Sequence key={`sfx-${it.shot.id}`} from={Math.max(0, it.from - 2)} durationInFrames={40} layout="none">
            <Audio src={src(kind)} volume={0.22} />
          </Sequence>
        ) : null;
      })}
      {items.map((it) =>
        it.shot.location && sfx.click ? (
          <Sequence key={`clk-${it.shot.id}`} from={it.from + 4} durationInFrames={30} layout="none">
            <Audio src={src(sfx.click)} volume={0.35} />
          </Sequence>
        ) : null,
      )}
      {project.bgm ? (
        <Audio
          src={src(project.bgm)}
          loop
          volume={(fr) => st.bgmVolume * Math.min(1, fr / 15, Math.max(0, (durationInFrames - fr) / 30))}
        />
      ) : null}
    </AbsoluteFill>
  );
};
