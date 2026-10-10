import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Odometer } from "../effects/numbers";
import type { StyleTokens } from "../styles/types";
import type { Shot } from "../types";
import { prog, ease, lerp } from "../effects/kit";

// Light-canvas price hook (see rules/taste.md anti-default; user pref: 浅色系).
// The number lands left→right; unit and place line settle only after it locks,
// so the first beat carries exactly one fact.
const CANVAS = "#F4F6FB";
const INK = "#1E2530";
const MUTED = "#5A6472";
const ACCENT = "#129E8C"; // rental accent deepened for the light canvas

/** Frames at which the reels have all locked (must match the Odometer params below). */
const LOCK_AT = 2 + 3 * 4 + 16;

export const HookShot: React.FC<{ shot: Shot; st: StyleTokens; duration: number }> = ({ shot, st, duration }) => {
  const f = useCurrentFrame();
  const num = shot.number;
  if (!num) return null;

  const unitK = prog(f, LOCK_AT - 6, LOCK_AT + 2, ease.outCubic);
  const placeK = prog(f, LOCK_AT + 2, LOCK_AT + 10, ease.outCubic);
  // Barely-there settle so the locked hold is never a frozen frame.
  const settle = lerp(prog(f, LOCK_AT, Math.max(LOCK_AT + 1, duration), ease.linear), 0, -6);

  return (
    <AbsoluteFill style={{ backgroundColor: CANVAS, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, width: 1440, top: 300, display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${settle}px)` }}>
        <div
          style={{
            fontFamily: st.fonts.sans,
            fontWeight: 700,
            fontSize: 30,
            letterSpacing: 8,
            color: ACCENT,
            opacity: prog(f, 0, 8),
            marginBottom: 26,
          }}
        >
          {num.caption ?? "月租金"}
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 22 }}>
          <Odometer value={num.value} st={st} size={200} color={INK} start={2} stagger={4} settle={16} />
          {num.unit ? (
            <div style={{ fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 52, color: INK, paddingBottom: 30, opacity: unitK, transform: `translateY(${lerp(unitK, 14, 0)}px)` }}>
              {num.unit}
            </div>
          ) : null}
        </div>
        <div style={{ marginTop: 40, height: 4, width: 96 * placeK, background: ACCENT, borderRadius: 2 }} />
        <div style={{ marginTop: 30, fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 36, color: MUTED, opacity: placeK }}>
          {shot.location?.main}
        </div>
      </div>
    </AbsoluteFill>
  );
};
