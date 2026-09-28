import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";

const PUNCT = /[，。！？；：、,.!?;:]/;

/** Split narration into short caption chunks (≤ maxChars, broken at punctuation) with proportional timing. */
export const chunkCaption = (text: string, maxChars = 13): string[] => {
  const out: string[] = [];
  let buf = "";
  for (const ch of [...text]) {
    if (PUNCT.test(ch)) {
      if (buf.trim()) out.push(buf.trim());
      buf = "";
      continue;
    }
    buf += ch;
    if ([...buf].length >= maxChars) {
      out.push(buf.trim());
      buf = "";
    }
  }
  if (buf.trim()) out.push(buf.trim());
  return out;
};

/** Burned-in captions for one narration segment (platform guidance requires subtitles). */
export const StyleCaptions: React.FC<{ text: string; st: StyleTokens; speechFrames: number; left?: number; right?: number; bottom?: number }> = ({ text, st, speechFrames, left = 60, right = 1380, bottom }) => {
  const f = useCurrentFrame();
  const chunks = chunkCaption(text);
  const lens = chunks.map((c) => [...c].length + 1);
  const total = lens.reduce((a, b) => a + b, 0) || 1;
  let acc = 0;
  let idx = chunks.length - 1;
  for (let i = 0; i < chunks.length; i++) {
    const end = ((acc + lens[i]) / total) * speechFrames;
    if (f < end) {
      idx = i;
      break;
    }
    acc += lens[i];
  }
  const cur = chunks[idx] ?? "";
  const width = right - left;
  const size = Math.min(st.caption.size, Math.floor((width - 40) / Math.max(1, [...cur].length)));
  return (
    <div style={{ position: "absolute", left, width, bottom: bottom ?? st.caption.bottom, display: "flex", justifyContent: "center" }}>
      <div style={{ fontFamily: st.fonts.sans, fontWeight: st.caption.weight, fontSize: size, lineHeight: 1.3, color: st.caption.color, textShadow: st.caption.shadow, whiteSpace: "nowrap", letterSpacing: 1, background: st.caption.box, padding: st.caption.box ? "2px 14px" : undefined, borderRadius: 6 }}>
        {cur}
      </div>
    </div>
  );
};
