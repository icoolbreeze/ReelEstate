// Floorplan + location effects. Motion grammar after video-shotcraft cards scan-bracket-sweep,
// scanline-annotate-focus and crash-zoom-punch (Apache-2.0). Re-skinned to StyleTokens.
// SPDX-License-Identifier: Apache-2.0
import React from "react";
import { useCurrentFrame } from "remotion";
import type { EffectProps } from "./types";
import { alpha, ease, lerp, prog, titleOf } from "./kit";

const W = 1440;
const H = 1080;

const Brackets: React.FC<{ x: number; y: number; w: number; h: number; color: string; k: number; len?: number; stroke?: number }> = ({ x, y, w, h, color, k, len = 60, stroke = 6 }) => {
  const d = (1 - k) * 60;
  const L = len;
  const s = { position: "absolute" as const, width: L, height: L, borderColor: color, borderStyle: "solid", opacity: k };
  return (
    <>
      <div style={{ ...s, left: x - d, top: y - d, borderWidth: `${stroke}px 0 0 ${stroke}px` }} />
      <div style={{ ...s, left: x + w - L + d, top: y - d, borderWidth: `${stroke}px ${stroke}px 0 0` }} />
      <div style={{ ...s, left: x - d, top: y + h - L + d, borderWidth: `0 0 ${stroke}px ${stroke}px` }} />
      <div style={{ ...s, left: x + w - L + d, top: y + h - L + d, borderWidth: `0 ${stroke}px ${stroke}px 0` }} />
    </>
  );
};

/** scan-bracket-sweep: four L brackets drop onto the room, a thin line with a gradient tail sweeps back and forth; content stays still. */
export const ScanBracket: React.FC<EffectProps> = ({ st, duration }) => {
  const f = useCurrentFrame();
  const k = prog(f, 2, 14, ease.outBack);
  const box = { x: 90, y: 90, w: W - 180, h: H - 300 };
  const sweeps = 3;
  const t = prog(f, 14, Math.max(30, duration - 12));
  const phase = (t * sweeps) % 1;
  const dir = Math.floor(t * sweeps) % 2 === 0 ? 1 : -1;
  const px = dir > 0 ? phase : 1 - phase;
  const lx = box.x + px * box.w;
  const out = 1 - prog(f, duration - 8, duration);
  return (
    <div style={{ position: "absolute", inset: 0, opacity: out }}>
      <Brackets {...box} color={st.accent} k={Math.min(1, Math.max(0, k))} />
      {f > 14 && t < 1 ? (
        <div style={{ position: "absolute", left: dir > 0 ? lx - 140 : lx, top: box.y, width: 140, height: box.h, background: `linear-gradient(${dir > 0 ? 90 : 270}deg, ${alpha(st.accent, 0)}, ${alpha(st.accent, 0.22)})`, borderRight: dir > 0 ? `3px solid ${st.accent}` : undefined, borderLeft: dir < 0 ? `3px solid ${st.accent}` : undefined }} />
      ) : null}
    </div>
  );
};

/** scanline-annotate-focus: a bright line scans top→bottom; where it passes, focus frames snap in (1.75x → 1) and a mono tag types beside. */
export const ScanlineFocus: React.FC<EffectProps> = ({ st, shot }) => {
  const f = useCurrentFrame();
  const y = lerp(prog(f, 0, 36, ease.linear), 60, H - 200);
  const lineOp = 1 - prog(f, 36, 42);
  const targets = [
    { x: 180, y: 260, w: 420, h: 280, tag: shot.room?.en?.toUpperCase() ?? "ROOM" },
    { x: 820, y: 520, w: 380, h: 240, tag: shot.room?.pill ?? "DETAIL" },
  ];
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {lineOp > 0 ? <div style={{ position: "absolute", left: 0, top: y, width: W, height: 3, background: st.accent, boxShadow: `0 0 16px ${alpha(st.accent, 0.8)}`, opacity: lineOp }} /> : null}
      {targets.map((tg, i) => {
        const at = ((tg.y - 60) / (H - 260)) * 36;
        const k = prog(f, at, at + 8, ease.outBack);
        const s = lerp(Math.min(1, Math.max(0, k)), 1.75, 1);
        const tagK = prog(f, at + 8, at + 16);
        return (
          <div key={i} style={{ position: "absolute", left: tg.x, top: tg.y, width: tg.w, height: tg.h, transform: `scale(${s})`, opacity: k > 0 ? 1 : 0 }}>
            <Brackets x={0} y={0} w={tg.w} h={tg.h} color={st.text} k={1} len={40} stroke={4} />
            <div style={{ position: "absolute", left: tg.w + 14, top: 0, fontFamily: "monospace", fontSize: 24, color: st.dark, background: st.accent, padding: "2px 10px", opacity: tagK, whiteSpace: "nowrap" }}>{tg.tag}</div>
          </div>
        );
      })}
    </div>
  );
};

/** crash-zoom-punch grammar for location: pin drops with a 6f punch, callout line + label extends. Replaces LocationLabel. */
export const PinCallout: React.FC<EffectProps> = ({ st, shot, project }) => {
  const f = useCurrentFrame();
  const main = shot.location?.main ?? titleOf(project);
  const sub = shot.location?.sub;
  const cx = 560;
  const cy = 520;
  const drop = prog(f, 0, 6, ease.outCubic);
  const bounce = prog(f, 6, 12) * (1 - prog(f, 12, 18));
  const ring = prog(f, 6, 26, ease.outCubic);
  const line = prog(f, 12, 22, ease.outCubic);
  const lab = prog(f, 18, 28, ease.outCubic);
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", left: cx - 90 * ring, top: cy - 30 * ring, width: 180 * ring, height: 60 * ring, borderRadius: "50%", border: `3px solid ${alpha(st.red, 1 - ring)}` }} />
      <div style={{ position: "absolute", left: cx - 28, top: lerp(drop, cy - 400, cy - 76) - bounce * 14, width: 56, height: 76 }}>
        <div style={{ width: 56, height: 56, borderRadius: "50% 50% 50% 0", transform: "rotate(-45deg)", background: st.red, boxShadow: "0 6px 14px rgba(0,0,0,.35)" }} />
        <div style={{ position: "absolute", left: 18, top: 18, width: 20, height: 20, borderRadius: 10, background: "#fff" }} />
      </div>
      <div style={{ position: "absolute", left: cx + 10, top: cy - 60, width: 120 * line, height: 3, background: st.text, transformOrigin: "left", transform: "rotate(-25deg)" }} />
      <div style={{ position: "absolute", left: cx + 120, top: cy - 170, opacity: lab, transform: `translateX(${lerp(lab, -20, 0)}px)` }}>
        <div style={{ fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: 88, color: st.text, textShadow: st.hardShadow ?? st.textGlow, whiteSpace: "nowrap" }}>{main}</div>
        {sub ? <div style={{ marginTop: 6, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 30, color: st.text, background: alpha(st.dark, 0.55), padding: "4px 12px", borderRadius: 6, display: "inline-block" }}>{sub}</div> : null}
      </div>
    </div>
  );
};

/** Reticle lock-on at the property: brackets close in on the centre, crosshair settles, label reads. Replaces LocationLabel. */
export const MapReticle: React.FC<EffectProps> = ({ st, shot, project }) => {
  const f = useCurrentFrame();
  const main = shot.location?.main ?? titleOf(project);
  const sub = shot.location?.sub;
  const k = prog(f, 0, 16, ease.outCubic);
  const size = lerp(k, 600, 300);
  const cx = W / 2;
  const cy = 390;
  const lock = f >= 16;
  const lab = prog(f, 18, 28, ease.outCubic);
  const col = lock ? st.accent : st.text;
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <Brackets x={cx - size / 2} y={cy - size / 2} w={size} h={size} color={col} k={1} len={64} stroke={7} />
      <div style={{ position: "absolute", left: cx - 1, top: cy - size / 2 + 20, width: 2, height: size - 40, background: alpha(col, 0.6) }} />
      <div style={{ position: "absolute", left: cx - size / 2 + 20, top: cy - 1, width: size - 40, height: 2, background: alpha(col, 0.6) }} />
      <div style={{ position: "absolute", left: cx - 12, top: cy - 12, width: 24, height: 24, borderRadius: 12, background: st.red, transform: `scale(${lock ? 1 + 0.25 * (1 - prog(f, 16, 24)) : 0})` }} />
      <div style={{ position: "absolute", left: 0, width: W, top: cy + size / 2 + 30, textAlign: "center", opacity: lab, transform: `translateY(${lerp(lab, 16, 0)}px)` }}>
        <div style={{ fontFamily: st.fonts.heavy, fontWeight: 900, fontSize: 84, color: st.text, textShadow: st.hardShadow ?? st.textGlow }}>{main}</div>
        {sub ? <div style={{ marginTop: 6, fontFamily: st.fonts.sans, fontWeight: 600, fontSize: 30, color: st.text, textShadow: st.textGlow }}>{sub}</div> : null}
      </div>
    </div>
  );
};
