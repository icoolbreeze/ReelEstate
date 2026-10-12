// Top-right social badge, persistent over the whole episode (MapHubHeygen). Handles come from the shared presenter profile
// (assets/presenter/<name>/presenter.yaml `social:`; an episode.yaml `social:` overrides), written to src/episode/social.json
// by pipeline/maphub/sync_assets.py. Icons: templates/map-hub/shared/public/social/ (staged into public/social/).
// Layout: one row top-right, 28 px safe margin, ends by y ~ 50 (the hook title starts at y 262, so no clash). Fade-in 12 f.
import React from "react";
import { Img, interpolate, staticFile, useCurrentFrame, Easing } from "remotion";
import SOCIAL from "../episode/social.json";
import { SANS } from "../fonts";

type Row = { platform: string; icon: string; handle: string };
const ROWS = ((SOCIAL as unknown as { rows?: Row[] }).rows ?? []).filter((r) => r.handle);

export const SocialBadge: React.FC<{ start?: number }> = ({ start = 6 }) => {
  const f = useCurrentFrame();
  if (!ROWS.length) return null;
  const q = interpolate(f, [start, start + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  // one quiet row, no pill/blur: icon 22 px + handle 18 px #F6F3EC @75 %, soft text shadow only; ends at y ~50
  return (
    <div style={{ position: "absolute", right: 28, top: 28, opacity: q, transform: `translateY(${(1 - q) * -6}px)`, display: "flex", alignItems: "center", gap: 22 }}>
      {ROWS.map((r) => (
        <div key={r.platform} style={{ display: "flex", alignItems: "center", gap: 7, height: 22 }}>
          <Img src={staticFile(r.icon)} style={{ width: 22, height: 22, objectFit: "contain", display: "block", opacity: 0.9, filter: "drop-shadow(0 1px 2px rgba(20,17,14,0.35))" }} />
          <span style={{ fontFamily: SANS, fontWeight: 500, fontSize: 18, lineHeight: 1, color: "rgba(246,243,236,0.75)", letterSpacing: 0.2, textShadow: "0 1px 3px rgba(20,17,14,0.45), 0 0 8px rgba(20,17,14,0.18)" }}>{r.handle}</span>
        </div>
      ))}
    </div>
  );
};
