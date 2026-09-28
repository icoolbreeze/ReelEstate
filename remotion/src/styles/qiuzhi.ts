import { F } from "./fonts";
import type { StyleTokens } from "./types";

// 秋芝风格：移植自 box v4 demo（remotion-realestate-v2/src/v4，demo-v4.json，v4-demo/REPORT.md）。
// 深紫底 + 黄色强调、数黑体硬投影、弹性 spring 入场、人像 全屏↔竖卡↔圆形小窗 变形。规则见 rules/style/qiuzhi.md。
export const QIUZHI: StyleTokens = {
  name: "qiuzhi",
  label: "秋芝",
  accent: "#FFD23F",
  text: "#FFFFFF",
  gold: "#FFD23F",
  red: "#FF8A3D",
  dark: "#0C0716",
  fonts: {
    roomZh: F.shuhei,
    roomZhWeight: 700,
    heavy: F.shuhei,
    sans: F.sans,
    latin: F.barlow,
    latinItalic: F.barlow,
  },
  roomSkewDeg: 0,
  grade: "saturate(1.05) contrast(1.02)",
  pushScale: 1.06,
  pushShare: 0.4,
  pip: { w: 232, h: 232, radius: 116, ring: "rgba(255,255,255,0.92)", margin: 56, bottom: 172, shape: "circle" },
  caption: {
    size: 50,
    weight: 800,
    color: "#FFFFFF",
    shadow: "0 0 3px rgba(0,0,0,.95), 0 0 3px rgba(0,0,0,.95), 0 3px 10px rgba(0,0,0,.6)",
    bottom: 176,
  },
  textGlow: "0 3px 10px rgba(0,0,0,.45)",
  hardShadow: "6px 6px 0 #6C3BE6",
  motion: "spring",
  enterFrames: 12,
  secondaryDelay: 10,
  loudnessLufs: -17,
  bgmVolume: 0.06,
  shotSeconds: [2.5, 5],
  stripBg: "rgba(12,7,22,0.55)",
  stripText: "rgba(255,255,255,0.92)",
};
