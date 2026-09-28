import React from "react";
import { useCurrentFrame } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { RoomInfo } from "../types";
import { E, pop, seg, typed, W } from "./util";

/** Conservative width of a Latin label in em (caps/digits ≈0.74 em in Montserrat 500, space 0.3 em). */
const estimateLabelWidth = (t: string) => [...t].reduce((w, c) => w + (c === " " ? 0.3 : /[A-Z0-9]/.test(c) ? 0.74 : /[\u3000-\u9fff]/.test(c) ? 1 : 0.6), 0);

/**
 * Space-tour room card (MediaStorm F-type "前厅 Lobby"), measured timeline from the hard cut (frame 0):
 * f10 filled dot pops in 4 frames (ease-out-back) · f16-18 outline dots · f24-26 Chinese name wipes in ·
 * f30 pill outline expands, floor text typed ~1 char/frame · f45-50 ">> ENGLISH" · fully built ≈1.5 s.
 * Sizes at 1440x1080: Chinese glyphs ≈180 px, pill 94 px, dots 75 px (110 px pitch). One accent colour.
 */
export const RoomCard: React.FC<{ room: RoomInfo; st: StyleTokens; y?: number }> = ({ room, st, y = 520 }) => {
  const f = useCurrentFrame();
  const spring = st.motion === "spring";
  const total = Math.max(1, Math.min(5, room.total ?? 3));
  const current = Math.max(1, Math.min(total, room.index ?? 1));
  const zhSize = 205; // ShuHeiTi glyph ≈ 0.88 em → ≈180 px
  const en = (room.en ?? "").toUpperCase();
  const enSize = en ? Math.min(96, Math.floor(560 / Math.max(4, 0.74 * [...en].length))) : 0;
  const zhWidth = [...room.zh].length * zhSize * 0.98;
  const blockW = Math.min(W - 120, zhWidth + (en ? 36 + 0.74 * enSize * [...en].length + enSize * 0.9 : 0));
  const left = (W - blockW) / 2;
  const top = y - 220;

  const dots = Array.from({ length: total }, (_, i) => {
    const isCur = i + 1 === current;
    const at = isCur ? 10 : 16 + Math.min(2, i);
    const p = pop(f, at, isCur ? 4 : 3);
    return (
      <div
        key={i}
        style={{
          position: "absolute",
          left: i * 110,
          top: 0,
          width: 75,
          height: 75,
          borderRadius: 38,
          boxSizing: "border-box",
          background: isCur ? st.accent : "transparent",
          border: isCur ? "none" : `5px solid ${st.accent}`,
          transform: `scale(${p.scale})`,
          opacity: p.k > 0 ? 1 : 0,
          boxShadow: isCur ? "0 2px 10px rgba(0,0,0,.25)" : undefined,
        }}
      />
    );
  });

  const wipe = seg(f, 24, spring ? 30 : 26, E.outCubic); // 2-3 frame wipe
  const pillK = seg(f, 30, 36, E.outCubic);
  const pillText = typed(room.pill ?? "", f, 32, 2); // 2 chars/frame: full label within ~5 f of the pill opening
  const enK = seg(f, 45, 50, E.outCubic);
  // Pill sizes to its full text (never clips): width is laid out by an invisible copy of the whole label,
  // the typed text overlays it. The font auto-shrinks so the pill fits the space right of the dots.
  const pillMax = Math.max(160, blockW - (total * 110 + 30));
  const pillFont = room.pill ? Math.min(58, Math.floor((pillMax - 64) / estimateLabelWidth(room.pill))) : 58;

  return (
    <div style={{ position: "absolute", left, top, width: blockW, height: 400 }}>
      {/* soft local vignette keeps white type readable on bright interiors */}
      <div style={{ position: "absolute", left: -140, top: -60, width: blockW + 280, height: 480, background: "radial-gradient(closest-side, rgba(0,0,0,.55), rgba(0,0,0,0))", opacity: seg(f, 6, 12) }} />
      <div style={{ position: "absolute", left: 0, top: 0, height: 94, width: blockW }}>
        <div style={{ position: "absolute", left: 0, top: 10 }}>{dots}</div>
        {room.pill ? (
          <div
            style={{
              position: "absolute",
              left: total * 110 + 30,
              top: 0,
              height: 94,
              borderRadius: 47,
              boxSizing: "border-box",
              border: `3px solid ${st.accent}`,
              transform: `scaleX(${pillK})`,
              transformOrigin: "left center",
              opacity: pillK > 0 ? 1 : 0,
              display: "flex",
              alignItems: "center",
              padding: "0 30px",
              fontFamily: st.fonts.latin,
              fontWeight: 500,
              fontSize: pillFont,
              letterSpacing: 1,
              color: st.text,
              whiteSpace: "nowrap",
              textShadow: st.textGlow,
            }}
          >
            <span style={{ visibility: "hidden" }}>{room.pill}</span>
            <span style={{ position: "absolute", left: 30, top: 0, lineHeight: "88px" }}>{pillText}</span>
          </div>
        ) : null}
      </div>
      <div style={{ position: "absolute", left: 0, top: 120, display: "flex", alignItems: "flex-end", gap: 36 }}>
        <div
          style={{
            fontFamily: st.fonts.roomZh,
            fontWeight: st.fonts.roomZhWeight,
            fontSize: zhSize,
            lineHeight: 1,
            color: st.text,
            transform: `skewX(${st.roomSkewDeg}deg)`,
            clipPath: `inset(0 ${(1 - wipe) * 100}% 0 0)`,
            textShadow: st.hardShadow ?? "0 4px 18px rgba(0,0,0,.35)",
            whiteSpace: "nowrap",
          }}
        >
          {room.zh}
        </div>
        {en ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              paddingBottom: 18,
              opacity: enK,
              transform: `translateX(${(1 - enK) * -24}px)`,
              fontFamily: st.fonts.latinItalic,
              fontStyle: "italic",
              fontWeight: 700,
              fontSize: enSize,
              color: st.text,
              whiteSpace: "nowrap",
              textShadow: st.textGlow,
            }}
          >
            <span style={{ color: st.accent, letterSpacing: -enSize * 0.12 }}>{">>"}</span>
            <span>{en}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
};
