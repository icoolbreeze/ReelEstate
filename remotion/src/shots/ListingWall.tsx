import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { StyleTokens } from "../styles/types";
import type { WallDoc } from "../types";
import { E, seg, src } from "./util";

const GRID: Record<number, [number, number]> = { 6: [3, 2], 7: [4, 2], 8: [4, 2], 9: [3, 3], 10: [4, 3], 11: [4, 3], 12: [4, 3] };

/**
 * Listing wall: 6-12 candidate cards on a 4:3 grid (cover, community, layout, area, rent, orientation, coarse floor).
 * Cards pop in staggered → the picked card is highlighted (others dim) → camera zooms into it as the hand-off to the detail shots.
 */
export const ListingWall: React.FC<{ wall: WallDoc; st: StyleTokens }> = ({ wall, st }) => {
  const f = useCurrentFrame();
  const { durationInFrames: d } = useVideoConfig();
  const cards = wall.cards.slice(0, 12);
  const n = Math.max(6, cards.length);
  const [cols, rows] = GRID[n] ?? [4, 3];
  const X0 = 70;
  const Y0 = 96;
  const GW = 1300;
  const GH = 830;
  const gap = 18;
  const cw = (GW - gap * (cols - 1)) / cols;
  const ch = (GH - gap * (rows - 1)) / rows;
  const coverH = ch - 96;
  const pickedIdx = Math.max(0, cards.findIndex((c) => c.id === wall.picked));
  const hl = seg(f, Math.round(d * 0.42), Math.round(d * 0.42) + 6, E.outCubic);
  const zoom = E.outCubic(seg(f, Math.round(d * 0.6), d - 1));
  const pc = pickedIdx % cols;
  const pr = Math.floor(pickedIdx / cols);
  const pcx = X0 + pc * (cw + gap) + cw / 2;
  const pcy = Y0 + pr * (ch + gap) + ch / 2;
  // Leave lower third for captions + PiP (~330 px). Final card ~900 px wide, centred slightly above mid.
  const targetScale = Math.min(900 / cw, 720 / ch);
  const s = interpolate(zoom, [0, 1], [1, targetScale]);
  const tx = interpolate(zoom, [0, 1], [0, 560 - pcx]); // keep clear of the right-hand PiP
  const ty = interpolate(zoom, [0, 1], [0, 430 - pcy]);
  const light = st.name === "mediastorm";
  const bg = light ? "#E9E7E3" : st.dark;
  const cardBg = light ? "#FFFFFF" : "#1D1530";
  const ink = light ? "#121212" : "#FFFFFF";
  const sub = light ? "#5B5B5B" : "rgba(255,255,255,.72)";
  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translate(${tx}px, ${ty}px) scale(${s})`, transformOrigin: `${pcx}px ${pcy}px` }}>
        {cards.map((c, i) => {
          const col = i % cols;
          const row = Math.floor(i / cols);
          const k = seg(f, i * 2, i * 2 + 6, E.outCubic);
          const picked = i === pickedIdx;
          const dimmed = !picked && hl > 0;
          const blur = wall.blur_others && !picked ? "blur(7px)" : undefined;
          return (
            <div
              key={c.id}
              style={{
                position: "absolute",
                left: X0 + col * (cw + gap),
                top: Y0 + row * (ch + gap),
                width: cw,
                height: ch,
                borderRadius: 10,
                background: cardBg,
                overflow: "hidden",
                opacity: k * (dimmed ? 1 - 0.62 * hl : 1),
                transform: `translateY(${(1 - k) * 18}px) scale(${picked ? 1 + 0.035 * hl : 1})`,
                boxShadow: picked && hl > 0 ? `0 0 0 ${6 * hl}px ${st.accent}, 0 16px 40px rgba(0,0,0,.28)` : "0 6px 18px rgba(0,0,0,.12)",
                filter: dimmed ? `grayscale(${hl})` : undefined,
                zIndex: picked ? 2 : 1,
              }}
            >
              {c.cover ? <Img src={src(c.cover)} style={{ width: "100%", height: coverH, objectFit: "cover", display: "block", filter: st.grade }} /> : <div style={{ height: coverH, background: "#bbb" }} />}
              <div style={{ padding: "10px 14px 0", filter: blur }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <div style={{ fontFamily: st.fonts.sans, fontWeight: 800, fontSize: 25, color: ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: cw * 0.6 }}>{c.community}</div>
                  <div style={{ fontFamily: st.fonts.latin, fontWeight: 700, fontSize: 24, color: ink }}>{c.rent}</div>
                </div>
                <div style={{ fontFamily: st.fonts.sans, fontWeight: 500, fontSize: 18, color: sub, marginTop: 6, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {[c.layout, c.area, c.orientation, c.floor].filter(Boolean).join(" · ")}
                </div>
              </div>
              {picked && hl > 0 ? (
                <div style={{ position: "absolute", left: 12, top: 12, background: st.accent, color: "#111", fontFamily: st.fonts.latin, fontWeight: 800, fontStyle: "italic", fontSize: 22, padding: "4px 12px", borderRadius: 4, opacity: hl }}>PICK</div>
              ) : null}
            </div>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
