import React from "react";
import { Img, staticFile, useCurrentFrame } from "remotion";
import { cameraProgress, flyScale, flyTranslate, flightSpring } from "./shared";

type Card = {
  roomIndex: number;
  w: number;
  h: number;
  left: number;
  top: number;
  rotDeg: number; // fixed, deterministic, in -4..+4
  rate: number; // multiplane parallax rate
  startFrame: number;
  from: { x: number; y: number };
  driftSign: 1 | -1; // adjacent cards drift with opposite signs
};

const CARDS: Card[] = [
  // far: upper right, flies out from behind the chest
  {
    roomIndex: 0, w: 220, h: 160, left: 1140, top: 120, rotDeg: -2, rate: 0.6,
    startFrame: 18, from: { x: 720, y: 560 }, driftSign: 1,
  },
  // mid: viewer left, slides in from off-canvas left
  {
    roomIndex: 1, w: 260, h: 190, left: 50, top: 460, rotDeg: 2.5, rate: 1.0,
    startFrame: 21, from: { x: -280, y: 520 }, driftSign: -1,
  },
  // near: viewer right, slides in from off-canvas right
  {
    roomIndex: 2, w: 300, h: 220, left: 1090, top: 570, rotDeg: -3, rate: 1.4,
    startFrame: 24, from: { x: 1520, y: 680 }, driftSign: 1,
  },
];

const CARD_SHADOW = "0 12px 28px rgba(38,48,58,.28)";

/** Three multi-plane room-photo cards, all below the person layer. */
export const RoomCards: React.FC<{ rooms: string[] }> = ({ rooms }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {CARDS.map((c) => {
        const s = flightSpring(frame, c.startFrame);
        if (s === null) return null;
        const center = { x: c.left + c.w / 2, y: c.top + c.h / 2 };
        const t = flyTranslate(s, c.from, center);
        const parScale = 1 + cameraProgress(frame) * 0.04 * c.rate;
        // Slow ~6px drift, opposite signs per card (period ~180 frames).
        const driftX = 6 * c.driftSign * Math.sin(frame * 0.035);
        const driftY = 6 * c.driftSign * Math.cos(frame * 0.035);
        return (
          <div
            key={c.roomIndex}
            style={{
              position: "absolute",
              left: c.left,
              top: c.top,
              width: c.w,
              height: c.h,
              borderRadius: 18,
              border: "6px solid #FFFFFF",
              boxShadow: CARD_SHADOW,
              backgroundColor: "#FFFFFF",
              overflow: "hidden",
              transform: `translate(${t.x + driftX}px, ${t.y + driftY}px) scale(${
                flyScale(s) * parScale
              }) rotate(${c.rotDeg}deg)`,
              transformOrigin: "50% 50%",
            }}
          >
            <Img
              src={staticFile(rooms[c.roomIndex])}
              style={{ display: "block", width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>
        );
      })}
    </>
  );
};
