// Floorplan + location effects. Motion grammar after video-shotcraft cards scan-bracket-sweep,
// scanline-annotate-focus and crash-zoom-punch (Apache-2.0). Re-skinned to StyleTokens.
// video-taste: frames stay inside action-safe and above the caption band; tags use the shared chip
// family; location sub-lines carry ≤1 middle dot each; labels clamp to [SAFE, W-SAFE].
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, bottomLimit, chip, CONTENT_BOTTOM, dotLines, ease, fitFont, ink, lerp, OFF_WHITE, prog, SAFE, scrim, shade, titleOf } from "./kit";

const W = 1440;

const Brackets: React.FC<{ x: number; y: number; w: number; h: number; color: string; k: number; len?: number; stroke?: number }> = ({ x, y, w, h, color, k, len = 60, stroke = 6 }) => {
  const d = (1 - k) * 60;
  const L = len;
  const s = { position: "absolute" as const, width: L, height: L, borderColor: color, borderStyle: "solid", opacity: Math.min(1, Math.max(0, k)) };
  return (
    <>
      <div style={{ ...s, left: x - d, top: y - d, borderWidth: `${stroke}px 0 0 ${stroke}px` }} />
      <div style={{ ...s, left: x + w - L + d, top: y - d, borderWidth: `${stroke}px ${stroke}px 0 0` }} />
      <div style={{ ...s, left: x - d, top: y + h - L + d, borderWidth: `0 0 ${stroke}px ${stroke}px` }} />
      <div style={{ ...s, left: x + w - L + d, top: y + h - L + d, borderWidth: `0 ${stroke}px ${stroke}px 0` }} />
    </>
  );
};

/** scan-bracket-sweep: four L brackets (one synchronized group) drop onto the room before the room card builds, a thin line sweeps back and forth. */
export const ScanBracket: React.FC<EffectProps> = ({ st, duration }) => {
  const f = useCurrentFrame();
  const k = prog(f, 0, 8, (t) => ease.outBack(t, 1.2));
  const box = { x: 96, y: 96, w: W - 192, h: CONTENT_BOTTOM - 96 };
  const sweeps = 3;
  const t = prog(f, 8, Math.max(30, duration - 6));
  const phase = (t * sweeps) % 1;
  const dir = Math.floor(t * sweeps) % 2 === 0 ? 1 : -1;
  const px = dir > 0 ? phase : 1 - phase;
  const lx = box.x + px * box.w;
  const out = 1 - prog(f, duration - 6, duration);
  return (
    <div style={{ position: "absolute", inset: 0, opacity: out }}>
      <Brackets {...box} color={st.accent} k={k} />
      {f > 8 && t < 1 ? (
        <div style={{ position: "absolute", left: dir > 0 ? lx - 140 : lx, top: box.y, width: 140, height: box.h, background: `linear-gradient(${dir > 0 ? 90 : 270}deg, ${alpha(st.accent, 0)}, ${alpha(st.accent, 0.2)})`, borderRight: dir > 0 ? `3px solid ${st.accent}` : undefined, borderLeft: dir < 0 ? `3px solid ${st.accent}` : undefined }} />
      ) : null}
    </div>
  );
};

/** scanline-annotate-focus: a bright line scans top→bottom; where it passes, focus frames snap in (1.75x → 1) and a chip tag reads above each frame. */
export const ScanlineFocus: React.FC<EffectProps> = ({ st, shot }) => {
  const f = useCurrentFrame();
  const y0 = 96;
  const y1 = CONTENT_BOTTOM;
  const y = lerp(prog(f, 0, 36, ease.linear), y0, y1);
  const lineOp = 1 - prog(f, 36, 42);
  const targets = [
    { x: 150, y: 250, w: 420, h: 260, tag: (shot.room?.en ?? "ROOM").toUpperCase() },
    { x: 860, y: 450, w: 380, h: 250, tag: "DETAIL" },
  ];
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {lineOp > 0 ? <div style={{ position: "absolute", left: SAFE, top: y, width: W - 2 * SAFE, height: 3, background: st.accent, boxShadow: shade(st, 0.35, 12, 0), opacity: lineOp }} /> : null}
      {targets.map((tg, i) => {
        const at = ((tg.y - y0) / (y1 - y0)) * 36;
        const k = prog(f, at, at + 8, (t) => ease.outBack(t, 1.2));
        const s = lerp(Math.min(1, Math.max(0, k)), 1.75, 1);
        const tagK = prog(f, at + 8, at + 16);
        const size = fitFont(tg.tag, 26, tg.w - 8, 16);
        return (
          <div key={i} style={{ position: "absolute", left: tg.x, top: tg.y, width: tg.w, height: tg.h, transform: `scale(${s})`, opacity: k > 0 ? 1 : 0 }}>
            <Brackets x={0} y={0} w={tg.w} h={tg.h} color={ink(st)} k={1} len={40} stroke={4} />
            <div style={{ position: "absolute", left: 0, top: -size - 22, ...chip(st), fontFamily: st.fonts.latin, fontWeight: 700, fontSize: size, color: st.accent, opacity: tagK }}>{tg.tag}</div>
          </div>
        );
      })}
    </div>
  );
};

/** Location sub-lines (≤1 middle dot each) as label-family chips. */
const SubChips: React.FC<{ sub?: string; st: EffectProps["st"]; k: number; maxWidth: number; align?: "flex-start" | "center" }> = ({ sub, st, k, maxWidth, align = "flex-start" }) =>
  sub ? (
    <div style={{ display: "flex", flexDirection: "column", alignItems: align, gap: 8, marginTop: 10, opacity: k }}>
      {dotLines(sub).map((l) => (
        <span key={l} style={{ ...chip(st), fontFamily: st.fonts.sans, fontWeight: 700, fontSize: fitFont(l, 30, maxWidth - 28, 20), color: ink(st) }}>{l}</span>
      ))}
    </div>
  ) : null;

/** crash-zoom-punch grammar for location: pin drops with a 6f punch, callout line + label extends. Replaces LocationLabel. */
export const PinCallout: React.FC<EffectProps> = ({ st, shot, project, zones }) => {
  const f = useCurrentFrame();
  const main = shot.location?.main ?? titleOf(project);
  const sub = shot.location?.sub;
  const cx = 520;
  const cy = 470;
  const drop = prog(f, 0, 6, ease.outCubic);
  const bounce = prog(f, 6, 10) * (1 - prog(f, 10, 15));
  const ring = prog(f, 6, 26, ease.outCubic);
  const line = prog(f, 12, 22, ease.outCubic);
  const lab = prog(f, 18, 28, ease.outCubic);
  const labelLeft = cx + 110;
  const maxW = W - SAFE - labelLeft;
  const mainSize = fitFont(main, 88, maxW);
  const nLines = sub ? dotLines(sub).length : 0;
  const blockH = mainSize * 1.1 + nLines * 52 + 10;
  const labelTop = Math.min(cy - 180, bottomLimit(zones, labelLeft, W - SAFE) - blockH);
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", left: cx - 90 * ring, top: cy - 30 * ring, width: 180 * ring, height: 60 * ring, borderRadius: "50%", border: `3px solid ${alpha(st.red, 1 - ring)}` }} />
      <div style={{ position: "absolute", left: cx - 28, top: lerp(drop, cy - 400, cy - 76) - bounce * 8, width: 56, height: 76 }}>
        <div style={{ width: 56, height: 56, borderRadius: "50% 50% 50% 0", transform: "rotate(-45deg)", background: st.red, boxShadow: shade(st, 0.4, 14, 6) }} />
        <div style={{ position: "absolute", left: 18, top: 18, width: 20, height: 20, borderRadius: 10, background: OFF_WHITE }} />
      </div>
      <div style={{ position: "absolute", left: cx + 10, top: cy - 60, width: 110 * line, height: 3, background: ink(st), transformOrigin: "left", transform: "rotate(-25deg)" }} />
      <div style={{ position: "absolute", left: labelLeft, top: labelTop, width: maxW, opacity: lab, transform: `translateX(${lerp(lab, -20, 0)}px)` }}>
        <div style={{ position: "absolute", left: -60, top: -40, width: Math.min(maxW, mainSize * [...main].length) + 120, height: mainSize + 80, ...scrim(st, 0.5) }} />
        <div style={{ position: "relative", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: mainSize, lineHeight: 1.1, color: ink(st), textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>{main}</div>
        <SubChips sub={sub} st={st} k={1} maxWidth={maxW} />
      </div>
    </div>
  );
};

/** Reticle lock-on at the property: brackets close in on the centre, crosshair settles, label reads. Replaces LocationLabel. */
export const MapReticle: React.FC<EffectProps> = ({ st, shot, project, zones, duration }) => {
  const f = useCurrentFrame();
  const main = shot.location?.main ?? titleOf(project);
  const sub = shot.location?.sub;
  const k = prog(f, 0, 16, ease.outCubic);
  const size = lerp(k, 560, 280);
  const cx = W / 2;
  const nLines = sub ? dotLines(sub).length : 0;
  const mainSize = fitFont(main, 84, W - 2 * 96);
  const labelH = mainSize * 1.1 + nLines * 52 + 10;
  // reticle + gap + label must end above the caption band / PiP
  const cy = Math.min(380, bottomLimit(zones, 96, W - 96) - labelH - 30 - 140);
  const lock = f >= 16;
  const lab = prog(f, 18, 28, ease.outCubic);
  const col = lock ? st.accent : ink(st);
  const breathe = 1 + 0.03 * prog(f, 16, duration, ease.linear); // slow push through the hold (no loop)
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: W, height: 1080, transform: `scale(${lock ? breathe : 1})`, transformOrigin: `${cx}px ${cy}px` }}>
        <Brackets x={cx - size / 2} y={cy - size / 2} w={size} h={size} color={col} k={1} len={64} stroke={7} />
        <div style={{ position: "absolute", left: cx - 1, top: cy - size / 2 + 20, width: 2, height: size - 40, background: alpha(col, 0.6) }} />
        <div style={{ position: "absolute", left: cx - size / 2 + 20, top: cy - 1, width: size - 40, height: 2, background: alpha(col, 0.6) }} />
        <div style={{ position: "absolute", left: cx - 12, top: cy - 12, width: 24, height: 24, borderRadius: 12, background: st.red, transform: `scale(${lock ? 1 + 0.12 * (1 - prog(f, 16, 24)) : 0})` }} />
      </div>
      <div style={{ position: "absolute", left: 96, width: W - 192, top: cy + 140 + 30, display: "flex", flexDirection: "column", alignItems: "center", opacity: lab, transform: `translateY(${lerp(lab, 16, 0)}px)` }}>
        <div style={{ position: "absolute", left: "20%", width: "60%", top: -40, height: mainSize + 80, ...scrim(st, 0.5) }} />
        <div style={{ position: "relative", fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: mainSize, lineHeight: 1.1, color: ink(st), textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>{main}</div>
        <SubChips sub={sub} st={st} k={1} maxWidth={W - 192} align="center" />
      </div>
    </div>
  );
};
