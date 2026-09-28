import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { StyleTokens } from "../styles/types";
import { E, seg, src } from "./util";

/**
 * Satellite push-in (map/satellite_4x3.jpg from map:fetch). Slow 1.0→1.28 push on the community point
 * (image centre), pulsing marker, and the imagery attribution always visible (left, above the platform UI).
 */
export const MapReveal: React.FC<{ image: string; attribution: string; st: StyleTokens; label?: string; showMarker?: boolean }> = ({ image, attribution, st, label, showMarker = true }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = E.outCubic(seg(f, 0, durationInFrames));
  const scale = interpolate(p, [0, 1], [1.0, 1.28]);
  const pulse = (f % 30) / 30;
  const mk = seg(f, 3, 9);
  return (
    <AbsoluteFill style={{ backgroundColor: "#111", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        <Img src={src(image)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "saturate(0.8) brightness(0.92) contrast(1.05)" }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 35%, rgba(0,0,0,.45) 100%)" }} />
      {showMarker ? (
        <div style={{ position: "absolute", left: 720, top: 540, width: 0, height: 0, opacity: mk }}>
          <div style={{ position: "absolute", left: -60 * pulse - 13, top: -60 * pulse - 13, width: 26 + 120 * pulse, height: 26 + 120 * pulse, borderRadius: "50%", border: `3px solid rgba(214,15,40,${0.8 * (1 - pulse)})` }} />
          <div style={{ position: "absolute", left: -17, top: -17, width: 34, height: 34, borderRadius: 17, background: "#D60F28", boxShadow: "0 0 0 5px #fff, 0 6px 16px rgba(0,0,0,.4)" }} />
          {label ? <div style={{ position: "absolute", left: 34, top: -26, whiteSpace: "nowrap", fontFamily: st.fonts.sans, fontWeight: 700, fontSize: 34, color: "#fff", background: "rgba(0,0,0,.55)", padding: "4px 14px", borderRadius: 6 }}>{label}</div> : null}
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 48, bottom: 44, fontFamily: st.fonts.sans, fontSize: 20, color: "rgba(255,255,255,.92)", textShadow: "0 1px 3px rgba(0,0,0,.8)" }}>{attribution}</div>
    </AbsoluteFill>
  );
};
