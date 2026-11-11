// Top-right social badge, persistent over the whole episode (MapHubHeygen). Handles come from the shared presenter profile
// (assets/presenter/<name>/presenter.yaml `social:`; an episode.yaml `social:` overrides), written to src/episode/social.json
// by pipeline/maphub/sync_assets.py. Icons: templates/map-hub/shared/public/social/ (staged into public/social/).
// Layout: one row top-right, 28 px safe margin, ends by y ~ 50 (the hook title starts at y 262, so no clash). Fade-in 12 f.
import React from "react";
import { Img, interpolate, staticFile, useCurrentFrame, Easing, getInputProps } from "remotion";

import { SANS } from "./fonts";

type Row = { platform: string; icon: string; handle: string };

export const ListingSocialBadge: React.FC<SocialProps> = ({ start = 6, rows: inputRows }) => {
  const ROWS = inputRows.filter((r) => r.handle);
  const f = useCurrentFrame();
  // per-export badge: input prop `badge` ("douyin" | "shipinhao" | "douyin,shipinhao"). Unset = template default: ONE row,
  // the render's `platform` prop (render_episode.py default "shipinhao" = 视频号), else the first row. Roughcuts leave badge unset (v8).
  const ip = getInputProps() as { badge?: string; platform?: string };
  const ALIAS: Record<string, string> = { shipinhao: "wechat-channels" };
  const want = String(ip.badge ?? ip.platform ?? "shipinhao").split(",").map((s) => ALIAS[s.trim()] ?? s.trim()).filter(Boolean);
  const hit = ROWS.filter((r) => want.includes(r.platform));
  const rows = hit.length ? hit : ROWS.slice(0, 1);
  if (!rows.length) return null;
  const q = interpolate(f, [start, start + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  // one quiet row, no pill/blur: icon 22 px + handle 18 px #F6F3EC @75 %, soft text shadow only; ends at y ~50
  return (
    <div style={{ position: "absolute", right: 28, top: 28, opacity: q, transform: `translateY(${(1 - q) * -6}px)`, display: "flex", alignItems: "center", gap: 22 }}>
      {rows.map((r) => (
        <div key={r.platform} style={{ display: "flex", alignItems: "center", gap: 7, height: 22 }}>
          <Img src={staticFile(r.icon)} style={{ width: 22, height: 22, objectFit: "contain", display: "block", opacity: 0.9, filter: "drop-shadow(0 1px 2px rgba(20,17,14,0.35))" }} />
          <span style={{ fontFamily: SANS, fontWeight: 500, fontSize: 18, lineHeight: 1, color: "rgba(246,243,236,0.75)", letterSpacing: 0.2, textShadow: "0 1px 3px rgba(20,17,14,0.45), 0 0 8px rgba(20,17,14,0.18)" }}>{r.handle}</span>
        </div>
      ))}
    </div>
  );
};


type SocialProps = { start?: number; rows: Row[] };
export const KnowledgeSocialBadge: React.FC<SocialProps> = ({ start = 6, rows: inputRows }) => {
  const ROWS = inputRows.filter((r) => r.handle);
  const f = useCurrentFrame();
  if (!ROWS.length) return null;
  const q = interpolate(f, [start, start + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  // Clean row with NO background, readable over any footage or dark canvas
  return (
    <div style={{
      position: "absolute",
      right: 32,
      top: 32,
      opacity: q,
      transform: `translateY(${(1 - q) * -6}px)`,
      display: "flex",
      alignItems: "center",
      gap: 20,
      background: "transparent",
      zIndex: 50
    }}>
      {ROWS.map((r) => (
        <div key={r.platform} style={{ display: "flex", alignItems: "center", gap: 8, height: 24 }}>
          <Img src={staticFile(r.icon)} style={{ width: 22, height: 22, objectFit: "contain", display: "block", filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.7))" }} />
          <span style={{
            fontFamily: SANS,
            fontWeight: 700,
            fontSize: 18,
            lineHeight: 1,
            color: "#0F172A",
            letterSpacing: 0.5,
            textShadow: "0 0 8px rgba(255,255,255,0.95), 0 1px 3px rgba(255,255,255,0.9)"
          }}>
            {r.handle}
          </span>
        </div>
      ))}
    </div>
  );
};

