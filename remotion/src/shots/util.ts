import { staticFile } from "remotion";
import { E, seg } from "../shared/motion";

export const W = 1440; // design canvas (4:3). Other ratios are scaled by ShotVideo.
export const H = 1080;
export const SAFE_BOTTOM = 150; // Douyin / Channels bottom UI (advice, not measured on-platform)
export const SAFE_RIGHT = 120;

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const isVideo = (f: string) => /\.(mp4|mov|webm|mkv)$/i.test(f);
export const src = (p: string) => (/^(https?:|data:)/.test(p) ? p : staticFile(p));
/** Characters of `text` visible when typing starts at frame f0 at `cpf` chars per frame. */
export const typed = (text: string, frame: number, f0: number, cpf = 1): string => {
  const chars = [...text];
  const n = Math.max(0, Math.floor((frame - f0 + 1) * cpf));
  return chars.slice(0, Math.min(chars.length, n)).join("");
};
export const pop = (frame: number, f0: number, dur: number) => {
  const k = seg(frame, f0, f0 + dur, E.linear);
  return { k, scale: k <= 0 ? 0 : E.outBack(k, 2.2) };
};
export { E, seg };
