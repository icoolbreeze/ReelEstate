import React, { useLayoutEffect, useRef, useState } from "react";
import { useCurrentFrame } from "remotion";
import { F } from "../../styles/fonts";
import { MEDIASTORM } from "../../styles/mediastorm";
import { flyScale, flyTranslate, flightSpring } from "./shared";

// Settled title geometry. Starting targets (~96 / ~200) do not fit the 240 px
// tall safe rect; shrunk the minimum amount while keeping the number at least
// 2x the label. Final sizes (see hook_matte/render report + layout.json):
const LABEL_SIZE = 80; // 「月租」 (target 96)
const NUM_SIZE = 167; // 「4800」 (target 200; 167/80 = 2.09x)
const TITLE_X = 72;
const TITLE_Y = 90;
const LINE1_BOX = 84; // 80 * 1.05
const LINE_GAP = 4;
const LINE2_TOP = TITLE_Y + LINE1_BOX + LINE_GAP; // 178
const LINE2_BOX = 175; // 167 * 1.05 = 175.4

const TEXT_SHADOW = "0 6px 24px rgba(0,0,0,.35)";
const FLY_FROM = { x: 720, y: 560 }; // behind the person; covered by the matte layer
const NUM_TEXT = "4800";
const NUM_FLIGHT_START = 10; // stagger (2f) after 「租」 which starts at frame 8
const TYPE_START = 18; // spring local frame 8 is settled; then one digit every 2 frames

const LABEL_GLYPHS = [
  { ch: "月", start: 6, center: { x: TITLE_X + LABEL_SIZE * 0.5, y: TITLE_Y + LINE1_BOX * 0.5 } },
  { ch: "租", start: 8, center: { x: TITLE_X + LABEL_SIZE * 1.5, y: TITLE_Y + LINE1_BOX * 0.5 } },
];

/** 「月租 4800」 assemble-then-type fly-in title. */
export const Title: React.FC<{ forceSettled?: boolean }> = ({ forceSettled = false }) => {
  const frame = useCurrentFrame();

  // Measure the full advance width of 「4800」 once so the group box never
  // shrinks while digits type on (hidden, still participates in layout).
  const numRef = useRef<HTMLDivElement>(null);
  const [numW, setNumW] = useState(0);
  useLayoutEffect(() => {
    if (numRef.current) setNumW(numRef.current.getBoundingClientRect().width);
  }, []);

  const visibleDigits = forceSettled
    ? 4
    : Math.max(0, Math.min(4, Math.floor((frame - TYPE_START) / 2) + 1));

  const numS = forceSettled ? 1 : flightSpring(frame, NUM_FLIGHT_START);
  const numCenter = { x: TITLE_X + numW / 2, y: LINE2_TOP + LINE2_BOX / 2 };

  return (
    <>
      <div
        ref={numRef}
        style={{
          position: "absolute",
          left: TITLE_X,
          top: LINE2_TOP,
          visibility: "hidden",
          pointerEvents: "none",
          whiteSpace: "nowrap",
          fontFamily: F.shuhei,
          fontWeight: 700,
          fontVariantNumeric: "tabular-nums",
          fontSize: NUM_SIZE,
        }}
      >
        {NUM_TEXT}
      </div>

      {LABEL_GLYPHS.map((g, i) => {
        const s = forceSettled ? 1 : flightSpring(frame, g.start);
        if (s === null) return null;
        const t = flyTranslate(s, FLY_FROM, g.center);
        return (
          <div
            key={g.ch}
            style={{
              position: "absolute",
              left: TITLE_X + i * LABEL_SIZE,
              top: TITLE_Y,
              width: LABEL_SIZE,
              height: LINE1_BOX,
              transform: `translate(${t.x}px, ${t.y}px) scale(${flyScale(s)})`,
              transformOrigin: "50% 50%",
            }}
          >
            <span
              style={{
                display: "block",
                width: "100%",
                lineHeight: `${LINE1_BOX}px`,
                textAlign: "center",
                fontFamily: F.shuhei,
                fontWeight: 700,
                fontSize: LABEL_SIZE,
                color: "#FFFFFF",
                textShadow: TEXT_SHADOW,
              }}
            >
              {g.ch}
            </span>
          </div>
        );
      })}

      {numS !== null && (
        <div
          style={{
            position: "absolute",
            left: TITLE_X,
            top: LINE2_TOP,
            width: numW,
            height: LINE2_BOX,
            // No overflow clipping: the text shadow must render outside the box.
            transform: (() => {
              const t = flyTranslate(numS, FLY_FROM, numCenter);
              return `translate(${t.x}px, ${t.y}px) scale(${flyScale(numS)})`;
            })(),
            transformOrigin: "50% 50%",
          }}
        >
          <span
            style={{
              display: "block",
              lineHeight: `${LINE2_BOX}px`,
              whiteSpace: "nowrap",
              fontFamily: F.shuhei,
              fontWeight: 700,
              fontVariantNumeric: "tabular-nums",
              fontSize: NUM_SIZE,
              color: MEDIASTORM.accent,
              textShadow: TEXT_SHADOW,
            }}
          >
            {NUM_TEXT.slice(0, visibleDigits)}
          </span>
        </div>
      )}
    </>
  );
};
