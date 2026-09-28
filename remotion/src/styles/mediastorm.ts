import { F } from "./fonts";
import type { StyleTokens } from "./types";

// 影视飓风（MediaStorm）风格：数值来自 /workspace/mediastorm/ANALYSIS.pdf 的逐帧测量（1920x1080 测，
// 高度方向原样用于 1440x1080）。规则说明见 rules/style/mediastorm.md。
export const MEDIASTORM: StyleTokens = {
  name: "mediastorm",
  label: "影视飓风",
  accent: "#D6EB00", // lime (sampled #D6EB00/#D2EB03); one accent per video
  text: "#FFFFFF",
  gold: "#ECCE70",
  red: "#D60F28",
  dark: "#141214",
  fonts: {
    roomZh: F.shuhei,
    roomZhWeight: 700,
    heavy: F.sans, // Noto Sans SC 900 ≈ 思源黑体 Heavy
    sans: F.sans,
    latin: F.latin,
    latinItalic: F.latin,
  },
  roomSkewDeg: -11,
  grade: "brightness(1.05) saturate(0.82) contrast(0.96)", // bright, low saturation (L* 55-60, sat 0.15-0.20)
  pushScale: 1.09,
  pushShare: 0.28, // 25-30% slow push-ins
  pip: { w: 330, h: 248, radius: 14, ring: "rgba(255,255,255,0.9)", margin: 140, bottom: 170, shape: "rect" },
  caption: { size: 42, weight: 600, color: "#FFFFFF", shadow: "0 2px 3px rgba(0,0,0,.55), 0 0 14px rgba(0,0,0,.35)", bottom: 172 },
  textGlow: "0 0 10px rgba(255,255,255,0.30), 0 2px 6px rgba(0,0,0,0.35)",
  motion: "cut",
  enterFrames: 8,
  secondaryDelay: 15,
  loudnessLufs: -16,
  bgmVolume: 0.1,
  shotSeconds: [2.7, 3.9],
  stripBg: "rgba(10,10,12,0.42)",
  stripText: "rgba(255,255,255,0.92)",
};
