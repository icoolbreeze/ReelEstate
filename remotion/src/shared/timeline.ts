import type { AudioSegment, Project, Segment } from "../types";

export type TimelineItem = { seg: Segment; from: number; duration: number; audio?: AudioSegment };

const CHARS_PER_SECOND = 4.5; // rough Mandarin narration speed
const PAD_SECONDS = 0.35;
const TAIL_SECONDS = 0.5;

export const estimateSeconds = (text: string): number => Math.max(2, [...text].length / CHARS_PER_SECOND);

export const buildTimeline = (p: Project, fps: number): TimelineItem[] => {
  let from = 0;
  return (p.narration?.segments ?? []).map((seg) => {
    const audio = p.audio?.find((a) => a.id === seg.id);
    const seconds = audio?.duration ?? estimateSeconds(seg.text);
    const duration = Math.max(fps, Math.round((seconds + PAD_SECONDS) * fps));
    const item: TimelineItem = { seg, from, duration, audio };
    from += duration;
    return item;
  });
};

export const totalFrames = (p: Project, fps: number): number => {
  const tl = buildTimeline(p, fps);
  const last = tl[tl.length - 1];
  return Math.max(fps * 2, (last ? last.from + last.duration : 0) + Math.round(TAIL_SECONDS * fps));
};
