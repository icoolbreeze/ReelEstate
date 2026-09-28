import type { StyleName } from "../types";

/** Design tokens for one style preset. Written rules live in rules/style/<name>.md. */
export type StyleTokens = {
  name: StyleName;
  label: string;
  accent: string; // the ONE accent colour of the video
  text: string;
  gold: string; // data numbers
  red: string; // over-limit numbers / location dot
  dark: string;
  fonts: {
    roomZh: string; // heavy Chinese for room titles
    roomZhWeight: number;
    heavy: string; // heavy sans for labels
    sans: string; // body / captions
    latin: string; // geometric Latin
    latinItalic: string;
  };
  roomSkewDeg: number; // synthetic italic for Chinese heavy titles (CJK fonts have no italics)
  grade: string; // CSS filter applied to footage
  pushScale: number; // slow push-in end scale
  pushShare: number; // share of media shots that get a push-in (documentation / fallback script)
  pip: { w: number; h: number; radius: number; ring: string; margin: number; bottom: number; shape: "rect" | "circle" };
  caption: { size: number; weight: number; color: string; shadow: string; box?: string; bottom: number };
  textGlow: string;
  hardShadow?: string; // qiuzhi: hard offset shadow on titles
  motion: "cut" | "spring"; // cut = hard-cut in with shot (mediastorm), spring = bouncy morphs (qiuzhi)
  enterFrames: number; // text card entrance length (4-12 frames for mediastorm)
  secondaryDelay: number; // secondary lines start (+12-18 frames)
  loudnessLufs: number;
  bgmVolume: number;
  shotSeconds: [number, number]; // target average shot length range
  stripBg: string;
  stripText: string;
};
