// @贝壳-TV map-hub 口播 (series preset "map-hub"): the map is the connective tissue of the whole talk.
//   opener (multiplane → scanline select → dolly zoom) lands on the map → host cursor clicks marks on the map
//   (input-trigger-moves · cursor-performance: bezier glide + wrist flick, hover, press, ripple, punch-in)
//   → the clicked mark opens into its segment (B-roll with scanline-annotate-focus tracking marks) → shrinks back into the mark.
//   L04: a single plain cursor glides in (no name tags).
// Everything is data: src/episode/{timeline,hub,pois,footage,annotations,episode,listings,brands}.json (see pipeline/).
import React from "react";
import { AbsoluteFill, Audio, Freeze, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import { NUM, SANS, TITLE } from "./fonts";
import TL from "./episode/timeline.json";
import HUB from "./episode/hub.json";
import POIS from "./episode/pois.json";
import FOOT from "./episode/footage.json";
import ANNS from "./episode/annotations.json";
import EP from "./episode/episode.json";
import DATA from "./episode/listings.json";
import { OPENER_NOTES, Opener, camAt, proj, Cam, TY, ROUTE, T as TO } from "./components/opener/Opener";
import { FlyText, shellStyle } from "./components/opener/TypeFly";
import { BrandStrip } from "./components/BrandStrip";
import { Mono } from "./components/opener/Opener";
import BRANDS from "./episode/brands.json";
import { ClipMedia, ScanAnnotate, Footage, Ann } from "./components/ScanAnnotate";
import { NamedCursor, Ripple, bez } from "./components/Cursor";
import { E_IO, E_OUT, FULL, H, PAL, Rect, W, lerp, lerpRect, seg } from "./lib";

type Cap = { text: string; f0: number; f1: number };
type Insert = { clip: string; mark: string; f0: number; f1: number; click: number };
type Line = { id: string; insert?: Insert; layout: "OPENER" | "A" | "PIP" | "MAP" | "B" | "END"; clip?: string; cam?: string; enter?: string; poi?: string[]; f0: number; f1: number; v0: number; v1: number; caps: Cap[]; click?: number; note?: string; big?: string; end?: boolean; fx?: string };
type Poi = { id: string; kind: string; label: string; sub: string; xy: number[]; walking_m?: number; driving_m?: number; walk_path?: number[][]; drive_path?: number[][] };
const LINES = TL.lines as unknown as Line[];
export const TOTAL = TL.total as number;
const OPEN_END = TL.opener as number;
// onScreenNotes=false (episode.json): only the bottom brand strip stays — no AI示意 / 示例数据 / AI数字人 / disclaimer labels
export const NOTES = (EP as any).onScreenNotes !== false;
OPENER_NOTES.on = NOTES;           // 240
const CAMS = HUB.cams as Record<string, Cam>;
const PO = POIS.pois as unknown as Poi[];
const FO = FOOT as unknown as Record<string, Footage>;
const AN = ANNS as unknown as Record<string, Ann>;
const LST = POIS.listing.xy as number[];
const CHOSEN = (DATA.mid as any[]).find((l) => l.id === DATA.chosenId);
const ACC = PAL.accent;

// ---------- click-switch timing (frames): glide → pause → press → open out of the mark; return mirrors it ----------
export const CLICK = { glide: 24, pause: 9, press: 11, open: 18, close: 18, pushZ: 1.6, cursor: 1.7 };   // press 11 f: ripple reaches ~70% of its radius by click+7, clip opens after   // press = press + full ripple before the clip opens
const OPEN_A = (click: number) => click + CLICK.press;            // transition starts once the press releases
// ---------- segment groups: a click on a mark opens a run of B lines; it closes back into the mark ----------
type Group = { mark: string; click: number; open1: number; end: number; close1: number; lines: Line[] };
const GROUPS: Group[] = [];
for (let i = 0; i < LINES.length; i++) {
  const L = LINES[i];
  if (!L.enter || L.click === undefined) continue;
  let j = i;
  while (j + 1 < LINES.length && LINES[j + 1].layout === "B" && !LINES[j + 1].enter) j++;
  const end = LINES[j].f1 + 4;
  GROUPS.push({ mark: L.enter, click: L.click, open1: OPEN_A(L.click) + CLICK.open, end, close1: end + CLICK.close, lines: LINES.slice(i, j + 1) });
}
// inserts: a short cut-away inside a map line (e.g. MET1 on the metro line): click the POI mark → clip opens from it → closes back
for (const L of LINES) {
  const I = L.insert; if (!I) continue;
  const pl = { id: `${L.id}_${I.clip}`, layout: "B", clip: I.clip, f0: I.f0, f1: I.f1, v0: I.f0, v1: I.f1, caps: [], click: I.click } as unknown as Line;
  GROUPS.push({ mark: I.mark, click: I.click, open1: OPEN_A(I.click) + CLICK.open, end: I.f1, close1: I.f1 + CLICK.close, lines: [pl] });
}
GROUPS.sort((a, b) => a.click - b.click);
const groupAt = (f: number) => GROUPS.find((g) => f >= g.click && f < g.close1);
// first frame of the END summary panel (hoisted so caption placement can reuse it)
const END0 = LINES.find((l) => l.layout === "END")?.v0 ?? 1e9;
const lineAt = (f: number) => { let r = LINES[0]; for (const l of LINES) if (l.v0 <= f) r = l; return r; };
const prevGroupClose = (L: Line) => { const g = GROUPS.filter((g) => g.close1 <= L.f0 + 1).pop(); return g ? g.close1 : -1; };
const aStart = (L: Line) => Math.max(L.v0, prevGroupClose(L));

// ---------- camera track ----------
type Key = { f: number; cam: Cam };
const KEYS: Key[] = [{ f: OPEN_END, cam: camAt(OPEN_END - 1) }];
for (const L of LINES) {
  if ((L.layout === "PIP" || L.layout === "MAP") && L.cam) KEYS.push({ f: Math.max(L.v0, prevGroupClose(L) - 12), cam: CAMS[L.cam] });
  if (L.enter && L.click !== undefined) KEYS.push({ f: L.click - 30, cam: CAMS[(HUB.enterCam as Record<string, string>)[L.enter]] ?? CAMS.community });
}
KEYS.sort((a, b) => a.f - b.f);
const DUR = 24;
const mixCam = (a: Cam, b: Cam, p: number): Cam => ({ s: a.s * Math.pow(b.s / a.s, p), fx: lerp(a.fx, b.fx, p), fy: lerp(a.fy, b.fy, p), tilt: lerp(a.tilt, b.tilt, p), P: lerp(a.P, b.P, p) });
// after each move the camera keeps a slow push + drift (no frozen map holds; shotcraft: no static window ≥0.8 s)
const evalKey = (start: Cam, k: Key, f: number): Cam => {
  const c = mixCam(start, k.cam, seg(f, k.f, k.f + DUR, E_IO));
  const h = Math.max(0, f - k.f - DUR * 0.6) / 30;
  return { ...c, s: c.s * (1 + 0.012 * h), fx: c.fx + 2.2 * h };
};
const START: Cam[] = [];
KEYS.forEach((k, i) => { START[i] = i === 0 ? k.cam : evalKey(START[i - 1], KEYS[i - 1], k.f); });
const camHub = (f: number): Cam => {
  if (f < OPEN_END) return camAt(f);
  let i = 0; for (let k = 0; k < KEYS.length; k++) if (KEYS[k].f <= f) i = k;
  return evalKey(START[i], KEYS[i], f);
};

// ---------- marks ----------
const HEAD = 88, HOFF = { x: 82, y: -58 };
const roomK = (c: Cam) => Math.min(1.05, Math.max(0.5, c.s / 2));
const CARD = { w: 150, h: 112 };
const markCenter = (id: string, c: Cam): number[] => {
  const G = proj(c, LST[0], LST[1]);
  const room = HUB.rooms.find((r) => r.id === id);
  if (room) { const k = roomK(c); return [G.x + HOFF.x + room.off[0] * k + (CARD.w * k) / 2, G.y + HOFF.y + room.off[1] * k + (CARD.h * k) / 2]; }
  if (id === HUB.env.id) { const p = proj(c, LST[0] + HUB.env.dxy[0], LST[1] + HUB.env.dxy[1]); return [p.x, p.y]; }
  const poi = PO.find((p) => p.id === id);
  if (poi) { const p = proj(c, poi.xy[0], poi.xy[1]); return [p.x, p.y]; }
  return [W / 2, H / 2];
};
const markRect = (id: string, c: Cam): Rect => {
  const [x, y] = markCenter(id, c);
  if (HUB.rooms.some((r) => r.id === id)) { const k = roomK(c); return { x: x - (CARD.w * k) / 2, y: y - (CARD.h * k) / 2, w: CARD.w * k, h: CARD.h * k }; }
  return { x: x - 36, y: y - 27, w: 72, h: 54 };
};

// ---------- click punch-in (map layer scales about the click point; cursor lives on the same layer) ----------
const zoomAt = (f: number) => {
  // push-in toward the target during the glide/pause, hold through the press, a little more while the clip opens, ease back on return
  const LEADF = CLICK.glide + CLICK.pause;
  const g = GROUPS.find((q) => f >= q.click - LEADF && f < q.close1);
  if (!g) return { z: 1, O: [W / 2, H / 2] };
  const O = markCenter(g.mark, camHub(Math.min(f, g.click)));
  const zp = CLICK.pushZ, zo = CLICK.pushZ * 1.08;
  const z = f < g.click ? lerp(1, zp, seg(f, g.click - LEADF, g.click - 3, E_IO)) : f < g.end ? lerp(zp, zo, seg(f, OPEN_A(g.click), g.open1, E_IO)) : lerp(zo, 1, seg(f, g.end, g.close1, E_IO));
  return { z, O };
};
const zoomRect = (r: Rect, z: number, O: number[]): Rect => ({ x: O[0] + (r.x - O[0]) * z, y: O[1] + (r.y - O[1]) * z, w: r.w * z, h: r.h * z });

// map PiP exclusion zone in SCREEN space: while that PiP is on screen the cursor must never be drawn inside it.
// PiP is right:50 / bottom:190 / 330×248. The NamedCursor tip sits at the anchor point but its 44px glyph renders at
// CLICK.cursor=1.7×, reaching ~69px right / ~72px down from the tip (svg offsets -3.2 / -1.6), so the rect must be
// expanded by the glyph extents plus 16px — then the *visible pointer* (not just the tip) clears the PiP border.
const PIP_R: Rect = { x: W - 50 - 330, y: H - 190 - 248, w: 330, h: 248 };
const PIP_GAP = 16;
const CUR_L = -3.2 * CLICK.cursor, CUR_R = (44 - 3.2) * CLICK.cursor, CUR_T = -1.6 * CLICK.cursor, CUR_B = (44 - 1.6) * CLICK.cursor;
const MAP_PIP_EXP: Rect = {
  x: PIP_R.x - CUR_R - PIP_GAP,
  y: PIP_R.y - CUR_B - PIP_GAP,
  w: PIP_R.w + CUR_R - CUR_L + 2 * PIP_GAP,
  h: PIP_R.h + CUR_B - CUR_T + 2 * PIP_GAP,
};
// nearest point OUTSIDE rect r to (px,py): if already outside, unchanged; else push to the closest edge
const clampOut = (px: number, py: number, r: Rect): number[] => {
  if (px < r.x || px > r.x + r.w || py < r.y || py > r.y + r.h) return [px, py];
  const d = [px - r.x, r.x + r.w - px, py - r.y, r.y + r.h - py];
  const m = Math.min(d[0], d[1], d[2], d[3]);
  if (m === d[0]) return [r.x - 1, py];
  if (m === d[1]) return [r.x + r.w + 1, py];
  if (m === d[2]) return [px, r.y - 1];
  return [px, r.y + r.h + 1];
};

// ---------- icons ----------
const TRAIN = '<path d="M21 13c0 -3.87 -3.37 -7 -10 -7h-8" /><path d="M3 15h16a2 2 0 0 0 2 -2" /><path d="M3 6v5h17.5" /><path d="M3 11v4" /><path d="M8 11v-5" /><path d="M13 11v-4.5" /><path d="M3 19h18" />';
const ICON: Record<string, string> = {
  metro: TRAIN,
  school: '<path d="M22 9L12 5 2 9l10 4 10-4v6"/><path d="M6 10.6V16a6 3 0 0 0 12 0v-5.4"/>',
  mall: '<path d="M6 7h12l1 13H5L6 7z"/><path d="M9 7a3 3 0 0 1 6 0"/>',
  market: '<path d="M3 10h18l-2 9H5l-2-9z"/><path d="M7 10l5-6 5 6"/>',
  hospital: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8v8M8 12h8"/>',
  park: '<path d="M12 3l6 9h-4l4 6H6l4-6H6l6-9z"/><path d="M12 18v3"/>',
  env: '<path d="M5 19c0-8 6-14 14-14 0 8-6 14-14 14z"/><path d="M5 19l8-8"/>',
};
const Icon: React.FC<{ k: string; size?: number; color?: string }> = ({ k, size = 24, color = PAL.ink }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: ICON[k] ?? ICON.env }} />
);
const distText = (p: Poi) => (p.kind === "hospital" && p.driving_m ? `驾车约 ${(p.driving_m / 1000).toFixed(1)} 公里`
  : (p.walking_m ?? 0) >= 1000 ? `步行约 ${((p.walking_m ?? 0) / 1000).toFixed(1)} 公里` : `步行 ${p.walking_m} 米`);

// ---------- map plane (same CSS camera as the opener's MapPlane) ----------
type PathDef = { d: number[][]; p: number; color: string; w: number; o: number };
// one shared builder: the map image, route <svg>, all markers and the cursor use the exact same transform
const camTransform = (c: Cam) => `translate3d(${720 - c.fx}px, ${540 + TY - c.fy}px, 0) rotateX(${c.tilt}deg) scale(${c.s})`;
const HubPlane: React.FC<{ c: Cam; paths: PathDef[]; children?: React.ReactNode }> = ({ c, paths, children }) => {
  const ext = EP.mapBase.ext;
  return (
    <div style={{ position: "absolute", inset: 0, perspective: c.P, perspectiveOrigin: "720px 540px" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1440, height: 1080, transformOrigin: `${c.fx}px ${c.fy}px`, transform: camTransform(c) }}>
        <Img src={staticFile(EP.mapBase.file)} style={{ position: "absolute", left: ext[0], top: ext[1], width: ext[2] - ext[0], height: ext[3] - ext[1] }} />
        <svg width={1440} height={1080} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
          {paths.filter((q) => q.p > 0.001).map((q, i) => {
            const d = q.d.map((p, k) => `${k ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");
            return (
              <g key={i} opacity={q.o}>
                <path d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.95} strokeWidth={(q.w + 6.5) / Math.max(0.6, c.s / 1.6)} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${q.p} 2`} />
                <path d={d} fill="none" stroke={q.color} strokeWidth={q.w / Math.max(0.6, c.s / 1.6)} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${q.p} 2`} />
              </g>
            );
          })}
        </svg>
        {children}
      </div>
    </div>
  );
};

// when is a POI in focus (label card + path)?
const focusSpans = (id: string) => LINES.filter((l) => l.poi?.includes(id)).map((l) => ({ a: l.click !== undefined ? l.click - 26 : l.v0, b: l.v1 }));
// const HUB0 = Math.max(OPEN_END, LINES.find((l) => l.layout !== "OPENER" && l.layout !== "A")?.v0 ?? OPEN_END);   // first frame the hub map is on screen
const REVEAL = { rooms: TO.titleA + 14, env: TO.titleA + 22, pois: TO.titleA + 30 };   // marks land during the opener title beat (after the pin morph) and carry into the hub   // marks first: everything lands right after the opener, routes come later

const POI_PART = (LINES.find((l) => l.poi?.length)?.v0 ?? 1e9);
// 小区环境 chip is plane-anchored under the env pin, but it must never touch the caption pill (Caption component:
// bottom 118, ~70px tall; the chip is ~27px tall). Its top is capped so the chip bottom stays >=16px above caption.
const ENV_CHIP_TOP = H - 118 - 70 - 16 - 27;
const Marks: React.FC<{ f: number; c: Cam; z: number; O: number[]; hot?: string; press?: number; overOpener?: boolean }> = ({ f, c, z, O, hot, press = 0, overOpener = false }) => {
  const G = proj(c, LST[0], LST[1]);
  const roomsO = 1 - seg(f, POI_PART - 6, POI_PART + 8);      // 样板间 cards + 小区环境 label step back once 周边配套 starts
  const hx = G.x + HOFF.x, hy = G.y + HOFF.y, k = roomK(c);
  // punch-in clipping: marks live inside the zoomed map layer (scale z about O), so a map-space box b is on
  // screen at O + (b - O) * z. While punching in, a label whose screen box leaves the 48px inset is hidden.
  // At z ≈ 1 every label kept today stays (no opener-edge regression).
  const INSET = 48;
  const punching = z > 1.05;
  const labelKept = (b: { x: number; y: number; w: number; h: number }) => {
    if (!punching) return true;
    const sx = O[0] + (b.x - O[0]) * z, sy = O[1] + (b.y - O[1]) * z;
    return sx >= INSET && sy >= INSET && sx + b.w * z <= W - INSET && sy + b.h * z <= H - INSET;
  };
  return (
    <>
      {/* POI pins + focused labels */}
      {PO.map((p, i) => {
        const ft = REVEAL.pois + i * 4;
        if (f < ft) return null;
        const q0 = proj(c, p.xy[0], p.xy[1]);
        // opener title beat: off-frame POIs sit at the frame edge (still visible, still at their bearing); hub framing is untouched
        const edge = f < OPEN_END + 12;
        const q = edge ? { x: Math.min(Math.max(q0.x, 60), W - 300), y: Math.min(Math.max(q0.y, 110), H - 220) } : q0;
        if (edge && (q.x !== q0.x || q.y !== q0.y) && q.x < 600 && q.y > 520) { q.x = 620; q.y = Math.min(q.y, H - 300); }   // keep the title block clear
        if (q.x < -100 || q.x > W + 100 || q.y < -100 || q.y > H + 60) return null;
        const spans = focusSpans(p.id);
        const cur = spans.find((s) => f >= s.a && f < s.b);
        const seen = spans.some((s) => f >= s.b);
        const lo = cur ? seg(f, cur.a, cur.a + 8, E_OUT) * (1 - seg(f, cur.b - 6, cur.b)) : 0;
        const r = 24 * (cur ? 1.12 : 0.92) * (hot === p.id ? 1.08 - 0.1 * press : 1);
        const isMetro = p.kind === "metro";
        if (overOpener && isMetro) return null;   // the opener draws its own metro mark/label
        return (
          <React.Fragment key={p.id}>
            <div style={{ position: "absolute", left: q.x - r, top: q.y - r, width: 2 * r, height: 2 * r, borderRadius: r, background: cur ? PAL.ink : PAL.card, border: `1px solid ${PAL.border}`, boxShadow: PAL.shadow, display: "flex", alignItems: "center", justifyContent: "center", ...shellStyle(f, [((i % 3) - 1) * 90, -110], ((i % 2) * 2 - 1) * 6, ft) }}>
              <Icon k={p.kind} size={24} color={cur ? "#FFF" : PAL.ink} />
            </div>
            {f >= ft + 6 && labelKept(lo > 0
              ? { x: q.x + r + 10, y: q.y - 34, w: Math.max(p.label.length * 22, p.sub.length * 15 + 8 + distText(p).length * 18) + 28, h: 86 }
              : { x: q.x + r + 10, y: q.y - 15, w: p.label.length * 14 + 18, h: 21 }) && (
              <div style={{ position: "absolute", left: q.x + r + 10, top: q.y - (lo > 0 ? 34 : 15), padding: lo > 0 ? "6px 14px 8px" : "2px 8px 3px", borderRadius: 10, background: lo > 0 ? PAL.card : "rgba(251,250,247,0.82)", boxShadow: lo > 0 ? PAL.shadow : undefined, fontFamily: SANS, whiteSpace: "nowrap", opacity: lo > 0 ? 1 : 0.85 * seg(f, ft + 6, ft + 14) * (seen || isMetro || cur ? 1 : 0.9) }}>
                {lo > 0 ? (
                  <>
                    <div style={{ fontWeight: 700, fontSize: 22, color: PAL.ink, lineHeight: 1.2 }}><FlyText seed={300 + i * 20} start={cur!.a + 2} step={1} runs={[{ s: p.label }]} /></div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8, lineHeight: 1.3 }}>
                      <span style={{ fontWeight: 500, fontSize: 15, color: PAL.sub }}>{p.sub}</span>
                      <span style={{ fontFamily: SANS, fontWeight: 700, fontSize: 18, color: ACC }}>{distText(p)}</span>
                    </div>
                  </>
                ) : <span style={{ fontWeight: 600, fontSize: 14, color: PAL.ink }}>{p.label}</span>}
              </div>
            )}
          </React.Fragment>
        );
      })}
      {/* 小区环境 pin (plane-anchored, 示意) */}
      {f >= REVEAL.env && (() => {
        const [x, y] = markCenter(HUB.env.id, c);
        const lit = hot === HUB.env.id ? 1 : 0;
        return (
          <>
            <div style={{ position: "absolute", left: x - 25, top: y - 25, width: 50, height: 50, borderRadius: 25, background: lit ? "#3E6B4A" : PAL.card, boxShadow: PAL.shadow, display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${1 + 0.06 * lit - 0.1 * lit * press})`, ...shellStyle(f, [-120, 60], -6, REVEAL.env) }}>
              <Icon k="env" color={lit ? "#FFF" : "#3E6B4A"} />
            </div>
            <div style={{ position: "absolute", left: x - 200, top: Math.min(y + 30, ENV_CHIP_TOP), width: 400, textAlign: "center", fontFamily: SANS, opacity: seg(f, REVEAL.env + 6, REVEAL.env + 12) * roomsO }}>
              <span style={{ padding: "3px 10px 4px", borderRadius: 8, background: "rgba(251,250,247,0.9)", fontWeight: 700, fontSize: 16, color: PAL.ink, whiteSpace: "nowrap" }}>{HUB.env.label}<span style={{ fontWeight: 500, fontSize: 13, color: PAL.sub, marginLeft: 6 }}>{HUB.env.sub}</span></span>
            </div>
          </>
        );
      })()}
      {/* listing pin: ground dot + leader + photo head (continues the opener's morph result) */}
      <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0 }}>
        {!overOpener && <line x1={G.x} y1={G.y} x2={hx - HEAD * 0.33} y2={hy + HEAD * 0.36} stroke={PAL.ink} strokeWidth={2.5} strokeLinecap="round" />}
        {!overOpener && <ellipse cx={G.x} cy={G.y} rx={8} ry={4.5} fill={ACC} stroke={PAL.ink} strokeWidth={1.5} />}
        {f >= REVEAL.rooms && roomsO > 0 && HUB.rooms.map((r) => {
          const [cx, cy] = markCenter(r.id, c);
          return <line key={r.id} x1={cx} y1={cy + (CARD.h * k) / 2} x2={hx} y2={hy - HEAD / 2} stroke={PAL.ink} strokeOpacity={0.45 * seg(f, REVEAL.rooms, REVEAL.rooms + 10)} strokeWidth={1.5} strokeDasharray="4 4" />;
        })}
      </svg>
      {!overOpener && <div style={{ position: "absolute", left: hx - HEAD / 2, top: hy - HEAD / 2, width: HEAD, height: HEAD, borderRadius: HEAD / 2, overflow: "hidden", boxShadow: "0 0 0 4px #FFFFFF, 0 10px 24px rgba(31,28,23,0.35)" }}>
        <Img src={staticFile(`photos_g/${CHOSEN.photo}`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>}
      {/* 样板间 photo cards fanned above the pin */}
      {f >= REVEAL.rooms && roomsO > 0 && HUB.rooms.map((r, i) => {
        const rc = markRect(r.id, c);
        const lit = hot === r.id ? 1 : 0;
        const rlw = (3 + r.label.length) * 17 * k + 20 * k + 6;   // 样板间 + r.label chip, pre-zoom map-space width
        return (
          <div key={r.id} style={{ position: "absolute", left: rc.x, top: rc.y, width: rc.w, height: rc.h, ...shellStyle(f, [(i - 1) * 140, 120], (i - 1) * 6, REVEAL.rooms + i * 4), opacity: Number(shellStyle(f, [0, 0], 0, REVEAL.rooms + i * 4).opacity) * roomsO }}>
            <div style={{ position: "absolute", inset: 0, borderRadius: 10 * k, overflow: "hidden", background: PAL.card, boxShadow: lit ? `0 0 0 ${3 * k}px ${ACC}, 0 14px 30px rgba(31,28,23,0.35)` : `0 0 0 ${3 * k}px #FFFFFF, ${PAL.shadow}`, transform: `scale(${1 + 0.05 * lit - 0.07 * lit * press})`, filter: lit ? "brightness(1.06)" : undefined }}>
              <Img src={staticFile(FO[(r as any).clip]?.still ?? r.photo)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              {NOTES && <div style={{ position: "absolute", left: 5 * k, top: 5 * k, padding: `${1 * k}px ${5 * k}px ${2 * k}px`, borderRadius: 4 * k, background: "rgba(20,18,20,0.72)", color: "#FBFBF8", fontFamily: SANS, fontWeight: 600, fontSize: 10 * k }}>AI示意</div>}
            </div>
            {hot !== r.id && labelKept({ x: rc.x + rc.w / 2 - rlw / 2, y: rc.y + rc.h + 6 * k, w: rlw, h: 17 * k * 1.3 + 6 * k }) && (
            <div style={{ position: "absolute", left: 0, right: 0, top: rc.h + 6 * k, textAlign: "center" }}>
              <span style={{ padding: `${2 * k}px ${10 * k}px ${3 * k}px`, borderRadius: 8 * k, background: lit ? PAL.ink : "rgba(251,250,247,0.92)", color: lit ? "#FFF" : PAL.ink, fontFamily: SANS, fontWeight: 700, fontSize: 17 * k, whiteSpace: "nowrap", boxShadow: PAL.shadow }}>
                <span style={{ fontWeight: 500, color: lit ? "#DDD" : PAL.sub, marginRight: 4 * k }}>样板间</span>{r.label}
              </span>
            </div>
            )}
          </div>
        );
      })}
    </>
  );
};

// ---------- opener end layout: every mark explained later, laid out once on the settled final camera ----------
// greedy placement with collision avoidance: each item tries a spiral of offsets around its true anchor and takes the first
// spot that clears already-placed items + fixed obstacles (title block, caption, credit bar, brand strip, listing pin);
// a leader line joins a displaced badge to its anchor dot. Computed once at module load (camera is still by then).
type OBox = { x: number; y: number; w: number; h: number };
const hit = (a: OBox, b: OBox, m = 10) => a.x < b.x + b.w + m && b.x < a.x + a.w + m && a.y < b.y + b.h + m && b.y < a.y + a.h + m;
const OM = { pin: 64, icon: 34, font: 26, card: { w: 210, h: 158 }, cardLabel: 42 };
type OItem = { id: string; kind: "room" | "poi" | "env"; label: string; ax: number; ay: number; box: OBox; order: number; photo?: string };
const OPENER_LAYOUT = (() => {
  const c = camAt(OPEN_END - 1);
  const G = proj(c, LST[0], LST[1]);
  const head = { x: G.x + HOFF.x, y: G.y + HOFF.y };
  const SAFE = { x0: 24, y0: 96, x1: W - 24, y1: 910 };   // y1 = top of the caption band (bottom 170px)
  const obst: OBox[] = [
    { x: 60, y: 735, w: 720, h: 175 },                         // lower-left title block
    { x: 0, y: 910, w: W, h: 170 },                            // caption band (bottom 170px): 小区环境 chip stays above it
    { x: W - 50 - 330, y: H - 190 - 248, w: 330, h: 248 },     // map PiP rect (bottom-right)
    { x: head.x - HEAD / 2 - 6, y: head.y - HEAD / 2 - 6, w: HEAD + 12, h: HEAD + 12 },   // listing photo head
    { x: G.x - 14, y: G.y - 10, w: 28, h: 20 },                // listing ground dot
  ];
  const used = new Set<string>(); for (const l of LINES) { (l.poi ?? []).forEach((x) => used.add(x)); if (l.enter) used.add(l.enter); if (l.insert) used.add(l.insert.mark); }
  const items: OItem[] = [];
  HUB.rooms.forEach((r, i) => { const [x, y] = markCenter(r.id, c); items.push({ id: r.id, kind: "room", label: r.label, ax: head.x, ay: head.y, box: { x: x - OM.card.w / 2, y: y - OM.card.h / 2 - 30, w: OM.card.w, h: OM.card.h + OM.cardLabel }, order: i, photo: FO[(r as any).clip]?.still ?? r.photo }); });
  const pw = (t: string) => OM.pin + 12 + t.length * OM.font + 26;
  { const [x, y] = markCenter(HUB.env.id, c); items.push({ id: HUB.env.id, kind: "env", label: HUB.env.label, ax: x, ay: y, box: { x: x - OM.pin / 2, y: y - OM.pin / 2, w: pw(HUB.env.label), h: OM.pin }, order: 3 }); }
  PO.filter((p) => used.has(p.id)).forEach((p, i) => { const q = proj(c, p.xy[0], p.xy[1]); items.push({ id: p.id, kind: "poi", label: p.label, ax: q.x, ay: q.y, box: { x: q.x - OM.pin / 2, y: q.y - OM.pin / 2, w: pw(p.label), h: OM.pin }, order: 4 + i }); });
  const placed: OBox[] = [];
  const offs: number[][] = [[0, 0]];
  for (let r = 1; r <= 40; r++) for (let a = 0; a < 24; a++) { const t = (a / 24) * Math.PI * 2; offs.push([Math.round(Math.cos(t) * r * 26), Math.round(Math.sin(t) * r * 22)]); }
  // flip candidates: label to the left of the pin
  for (const it of items) {
    const b0 = { ...it.box };
    const clampB = (b: OBox) => ({ ...b, x: Math.min(Math.max(b.x, SAFE.x0), SAFE.x1 - b.w), y: Math.min(Math.max(b.y, SAFE.y0), SAFE.y1 - b.h) });
    let best: OBox | null = null;
    for (const [dx, dy] of offs) {
      const b = clampB({ ...b0, x: b0.x + dx, y: b0.y + dy });
      if (!obst.some((o) => hit(b, o)) && !placed.some((o) => hit(b, o, 12))) { best = b; break; }
    }
    it.box = best ?? clampB(b0);
    placed.push(it.box);
  }
  return items;
})();
const OpenerMarks: React.FC<{ f: number; g?: Group; z: number; O: number[] }> = ({ f, g, z, O }) => {
  // during a click punch-in: pressed card rect in screen space (the map layer is scaled about O); frame inset 48px
  const pressRect = g ? zoomRect(markRect(g.mark, camHub(g.click)), z, O) : null;
  const INSET = 48;
  const hidden = (it: OItem) => {
    // it.box lives in pre-zoom map space: convert it through the same zoom (scale z about O) into screen space before
    // testing. At z=1 the box is unchanged, so edge labels stay when there is no punch-in.
    const b = zoomRect(it.box, z, O);
    if (b.x < INSET || b.y < INSET || b.x + b.w > W - INSET || b.y + b.h > H - INSET) return true;
    if (pressRect) return b.x < pressRect.x + pressRect.w && pressRect.x < b.x + b.w && b.y < pressRect.y + pressRect.h && pressRect.y < b.y + b.h;
    return false;
  };
  return (
  <>
    <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0 }}>
      {OPENER_LAYOUT.map((it) => {
        const t0 = REVEAL.rooms + it.order * 4;
        const o = seg(f, t0 + 4, t0 + 12) * (hidden(it) ? 0 : 1);
        const px = it.kind === "room" ? it.box.x + it.box.w / 2 : it.box.x + OM.pin / 2, py = it.kind === "room" ? it.box.y + OM.card.h : it.box.y + OM.pin / 2;
        const inF = it.ax > 0 && it.ax < W && it.ay > 90 && it.ay < 990;   // off-frame anchor: badge sits at the edge, no leader across the frame
        const far = inF && Math.hypot(px - it.ax, py - it.ay) > 34;
        return (
          <g key={it.id} opacity={o}>
            {(far || it.kind === "room") && inF && <line x1={it.ax} y1={it.ay} x2={px} y2={py} stroke="#FFFFFF" strokeWidth={5} strokeLinecap="round" />}
            {(far || it.kind === "room") && inF && <line x1={it.ax} y1={it.ay} x2={px} y2={py} stroke={PAL.ink} strokeWidth={2} strokeDasharray={it.kind === "room" ? "5 5" : undefined} strokeLinecap="round" />}
            {it.kind !== "room" && inF && <circle cx={it.ax} cy={it.ay} r={7} fill={ACC} stroke="#FFFFFF" strokeWidth={2.5} />}
          </g>
        );
      })}
    </svg>
    {OPENER_LAYOUT.map((it) => {
      const t0 = REVEAL.rooms + it.order * 4;
      if (f < t0 || hidden(it)) return null;
      const sh = shellStyle(f, [((it.order % 3) - 1) * 110, -120], ((it.order % 2) * 2 - 1) * 6, t0);
      if (it.kind === "room") return (
        <div key={it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, width: OM.card.w, ...sh }}>
          <div style={{ position: "relative", width: OM.card.w, height: OM.card.h, borderRadius: 12, overflow: "hidden", boxShadow: `0 0 0 4px #FFFFFF, ${PAL.shadow}` }}>
            <Img src={staticFile(it.photo!)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            {NOTES && <div style={{ position: "absolute", left: 7, top: 7, padding: "2px 7px 3px", borderRadius: 5, background: "rgba(20,18,20,0.72)", color: "#FBFBF8", fontFamily: SANS, fontWeight: 600, fontSize: 14 }}>AI示意</div>}
          </div>
          <div style={{ marginTop: 8, textAlign: "center" }}>
            <span style={{ padding: "3px 12px 4px", borderRadius: 9, background: "rgba(251,250,247,0.95)", color: PAL.ink, fontFamily: SANS, fontWeight: 700, fontSize: 24, whiteSpace: "nowrap", boxShadow: PAL.shadow }}>
              <span style={{ fontWeight: 500, color: PAL.sub, marginRight: 6, fontSize: 20 }}>样板间</span>{it.label}
            </span>
          </div>
        </div>
      );
      const kind = it.kind === "env" ? "env" : PO.find((p) => p.id === it.id)!.kind;
      return (
        <div key={it.id} style={{ position: "absolute", left: it.box.x, top: it.box.y, height: OM.pin, display: "flex", alignItems: "center", ...sh }}>
          <div style={{ width: OM.pin, height: OM.pin, borderRadius: OM.pin / 2, background: it.kind === "env" ? "#3E6B4A" : PAL.card, border: "3px solid #FFFFFF", boxShadow: PAL.shadow, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
            <Icon k={kind} size={OM.icon} color={it.kind === "env" ? "#FFF" : PAL.ink} />
          </div>
          <div style={{ marginLeft: 8, padding: "4px 12px 6px", borderRadius: 10, background: "rgba(251,250,247,0.95)", boxShadow: PAL.shadow, fontFamily: SANS, fontWeight: 700, fontSize: OM.font, color: PAL.ink, whiteSpace: "nowrap" }}>{it.label}</div>
        </div>
      );
    })}
  </>
  );
};

// ---------- cursor choreography ----------
type CEv = { f: number; id: string; click: boolean };
const CEVENTS: CEv[] = [];
for (const L of LINES) {
  if (L.enter && L.click !== undefined) CEVENTS.push({ f: L.click, id: L.enter, click: true });
  else if (L.layout === "PIP" && L.poi?.length) CEVENTS.push({ f: L.v0 + 22, id: L.poi[0], click: false });
  if (L.insert) CEVENTS.push({ f: L.insert.click, id: L.insert.mark, click: true });
}
CEVENTS.sort((a, b) => a.f - b.f);
const REST = [1130, 820];
const cursorAt = (f: number) => {
  const LEAD = CLICK.glide + CLICK.pause;
  let i = -1; for (let k = 0; k < CEVENTS.length; k++) if (CEVENTS[k].f - LEAD <= f) i = k;
  const tgt = (e: CEv) => { const [x, y] = markCenter(e.id, camHub(e.f)); return [x + 6, y + 4]; };
  if (i < 0) return { x: REST[0], y: REST[1], hot: undefined as string | undefined, ev: undefined as CEv | undefined };
  const e = CEVENTS[i];
  const from = i > 0 ? tgt(CEVENTS[i - 1]) : REST;
  const a = Math.max(e.f - LEAD, i > 0 ? CEVENTS[i - 1].f + 4 : -1);
  const t = seg(f, a, e.f - CLICK.pause, E_IO);                    // ease-in/out glide, then a visible pause on the mark
  const [x, y] = bez(from, tgt(e), t);
  const drift = f > e.f + 4 ? [Math.sin(f * 0.055) * 6 + Math.sin(f * 0.021) * 4, Math.cos(f * 0.047) * 4] : [0, 0];
  return { x: x + drift[0], y: y + drift[1], hot: f >= e.f - CLICK.pause ? e.id : undefined, ev: e };
};

// ---------- pieces ----------
const Caption: React.FC<{ text: string; right?: boolean; size?: number }> = ({ text, right, size = 46 }) => (
  <div style={{ position: "absolute", left: right ? undefined : 0, right: right ? 70 : 0, width: right ? undefined : W, bottom: 118, textAlign: right ? "right" : "center" }}>
    <span style={{ display: "inline-block", padding: "6px 18px 9px", borderRadius: 10, background: "rgba(18,16,14,0.48)", color: "#FFFFFF", fontFamily: SANS, fontWeight: 700, fontSize: size, letterSpacing: 1, textShadow: "0 1px 3px rgba(0,0,0,0.4)", whiteSpace: "nowrap" }}>{text}</span>
  </div>
);
const GRADE_A = "contrast(1.04) saturate(0.88) sepia(0.06)";
const presenterFo = (id?: string): Footage => {
  const fo = id ? FO[id] : undefined;
  if (fo && fo.kind !== "pending") return fo;
  return { kind: "video", src: (HUB.presenterPlaceholders as Record<string, string>)[id ?? "P1"] ?? "placeholder/H1.mp4", w: 1088, h: 816, fps: 30, status: "placeholder" };
};
// ---------- HeyGen avatar segments (footage/heygen/<seg>.mp4, ids HG..): lip-synced to the line audio, so the segment starts
// HG_PAD frames before the line's first word (the export keeps a 0.25 s handle) and holds its first frame before that ----------
export const HG_PAD = 8;
const isHG = (id?: string) => !!id && id.startsWith("HG");
export const AvatarBadge: React.FC<{ x: number; y: number; size?: number; o?: number }> = ({ x, y, size = 15, o = 1 }) => (
  <div style={{ position: "absolute", left: x, top: y, opacity: o, padding: "3px 10px 4px", borderRadius: 6, background: "rgba(20,18,16,0.62)", color: "#FFF", fontFamily: SANS, fontWeight: 700, fontSize: size, letterSpacing: 1, whiteSpace: "nowrap" }}>AI数字人 · AI合成声音</div>
);
const PresenterClip: React.FC<{ L: Line; f: number; from: number }> = ({ L, f, from }) => {
  const fo = presenterFo(L.clip);
  if (!isHG(L.clip)) return <Sequence from={from} layout="none"><ClipMedia fo={fo} id={L.clip ?? "P1"} local={f - from} inFrame={inFor(L, fo)} grade={GRADE_A} /></Sequence>;
  const s0 = L.f0 - HG_PAD;
  if (f < s0) return <Freeze frame={0}><ClipMedia fo={fo} id={L.clip!} local={0} inFrame={0} grade={GRADE_A} /></Freeze>;
  return <Sequence from={s0} layout="none"><ClipMedia fo={fo} id={L.clip!} local={f - s0} inFrame={0} grade={GRADE_A} /></Sequence>;
};
// presenter in-point: varied per line; the sign-off line ends on the clip's last frames (the Muse presenter waves goodbye there)
const inFor = (L: Line, fo: Footage) => { const len = Math.round((fo.dur ?? 10) * 30); const need = L.v1 - L.v0; return Math.max(0, L.end ? len - need - 3 : Math.min(len - need - 4, (LINES.indexOf(L) * 47) % 90)); };

export const MapHubKoubo: React.FC = () => {
  const f = useCurrentFrame();
  const L = lineAt(f);
  const c = camHub(f);
  const g = groupAt(f);
  const { z, O } = zoomAt(f);
  const cur = cursorAt(f);
  const hub = f >= OPEN_END - 2;

  // paths on the plane: metro route (opener's snapped polyline) + walking routes of focused POIs
  const paths: PathDef[] = [];
  { const s = focusSpans("metro"); const first = s[0]; if (first && f >= first.a) paths.push({ d: ROUTE as number[][], p: seg(f, first.a + 4, first.a + 34, E_IO), color: ACC, w: 6.5, o: 1 }); }
  for (const p of PO) {
    const dpath = p.kind === "hospital" && p.drive_path ? p.drive_path : p.walk_path;   // the drawn route matches the distance on the label
    if (p.kind === "metro" || !dpath) continue;
    const s = focusSpans(p.id); const sp = s.find((q) => f >= q.a && f < q.b) ?? s.filter((q) => f >= q.b).pop();
    if (!sp) continue;
    const on = f < sp.b;
    paths.push({ d: dpath, p: seg(f, sp.a + 4, sp.a + 30, E_IO), color: p.kind === "hospital" ? "#5A6E86" : PAL.ink, w: 5, o: on ? 0.95 : 0.3 });
  }

  // overlays
  const showA = L.layout === "A" && f >= aStart(L);
  let rect: Rect | null = null, open = 0;
  if (g) {
    if (f < g.end) { const p = seg(f, OPEN_A(g.click), g.open1, E_IO); rect = lerpRect(zoomRect(markRect(g.mark, camHub(g.click)), z, O), FULL, p); open = p; }
    else { const p = seg(f, g.end, g.close1, E_IO); rect = lerpRect(FULL, zoomRect(markRect(g.mark, c), z, O), p); open = 1 - p; }
  }
  const gLine = g ? (g.lines.filter((l) => l.v0 <= f || l === g.lines[0]).pop() ?? g.lines[0]) : undefined;
  const gStart = (l: Line) => (g && l === g.lines[0] ? g.click : l.v0);
  const endP = seg(f, END0, END0 + 14, E_IO);
  const dark = Math.max(showA ? 1 : open, endP);
  const openerO = 1 - seg(f, OPEN_END, OPEN_END + 12);

  // caption chunk
  const capLine = LINES.find((l) => f >= l.f0 && f < l.f1 + 8);
  const cap = capLine ? capLine.caps.filter((q) => q.f0 <= f).pop() ?? capLine.caps[0] : undefined;

  const credit = f < 130 ? "房源照片为AI示意或图库示意" : showA ? (isHG(L.clip) ? "AI数字人 · AI合成声音" : "主持人画面为AI生成") : open > 0.5 ? "AI生成示意 非实拍" : EP.mapBase.credit;

  return (
    <AbsoluteFill style={{ background: PAL.land, overflow: "hidden" }}>
      <Audio src={staticFile("episode/mix.wav")} />
      {/* ===== hub map world (zoom layer: plane + marks + cursor share one transform so the click point never drifts) ===== */}
      {hub && (
        <AbsoluteFill style={{ transform: `scale(${z})`, transformOrigin: `${O[0]}px ${O[1]}px` }}>
          <HubPlane c={c} paths={paths} />
          <AbsoluteFill style={{ background: `linear-gradient(180deg, ${PAL.land}C8 0%, ${PAL.land}00 13%, ${PAL.land}00 70%, ${PAL.land}C0 96%)` }} />
          <Marks f={f} c={c} z={z} O={O} hot={cur.hot} press={cur.ev?.click ? seg(f, cur.ev.f - 2, cur.ev.f + 1) * (1 - seg(f, cur.ev.f + 6, cur.ev.f + 10)) : 0} />
        </AbsoluteFill>
      )}

      {/* ===== opener (0–240), fades into the identical hub map ===== */}
      {openerO > 0 && (
        <Sequence durationInFrames={OPEN_END + 12}>
          <AbsoluteFill style={{ opacity: openerO }}><Opener theme="light" map="flovaSat3Db" strip={false} chrome={false} drawRoute={false} metroMark={false} /></AbsoluteFill>
        </Sequence>
      )}
      {/* every mark explained later lands on the opener's final map (same camera as the hub, so nothing re-pops after the hand-off) */}
      {f >= REVEAL.rooms && f < OPEN_END + 12 && <AbsoluteFill style={{ opacity: openerO }}><OpenerMarks f={f} g={g} z={z} O={O} /></AbsoluteFill>}

      {/* ===== PiP presenter on map lines ===== */}
      {L.layout === "PIP" && !g && (() => {
        return (
          <div style={{ position: "absolute", right: 50, bottom: 190, width: 330, height: 248, borderRadius: 14, overflow: "hidden", border: "2px solid #FFFFFF", boxShadow: "0 12px 30px rgba(31,28,23,0.35)" }}>
            <div style={{ width: W, height: H, transform: `scale(${330 / W})`, transformOrigin: "0 0" }}><PresenterClip L={L} f={f} from={L.v0} /></div>
          </div>
        );
      })()}
      {NOTES && L.layout === "PIP" && !g && isHG(L.clip) && <AvatarBadge x={W - 50 - 330 + 8} y={H - 190 - 248 - 34} size={14} />}

      {/* ===== segment overlay: opens out of the clicked mark, B-roll + scanline-annotate-focus, shrinks back ===== */}
      {g && rect && gLine && f >= OPEN_A(g.click) && (() => {
        const fo = FO[gLine.clip!] ?? ({ kind: "pending", status: "pending", purpose: gLine.clip } as Footage);
        const local = f - gStart(gLine);
        const sx = rect.w / W, sy = rect.h / H;
        const full = f >= g.open1 && f < g.end;
        const title = HUB.rooms.find((r) => r.id === g.mark)?.label ?? (g.mark === HUB.env.id ? HUB.env.label : PO.find((p) => p.id === g.mark)?.label ?? "");
        const kicker = HUB.rooms.some((r) => r.id === g.mark) ? (NOTES ? "样板间 · AI示意" : "样板间") : g.mark === HUB.env.id ? (NOTES ? "小区环境 · AI示意" : "小区环境") : "周边配套";
        const tag = !NOTES ? undefined : (HUB.clipTags as Record<string, string> | undefined)?.[gLine.clip!];
        return (
          <div style={{ position: "absolute", left: rect.x, top: rect.y, width: rect.w, height: rect.h, borderRadius: lerp(Math.min(rect.h / 2, 14 / Math.min(sx, sy)), 0, open) * Math.min(sx, sy), overflow: "hidden", boxShadow: open < 0.98 ? "0 20px 50px rgba(0,0,0,0.35)" : undefined }}>
            <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${sx}, ${sy})`, transformOrigin: "0 0" }}>
              {g.lines.map((l) => (l === gLine ? (
                <Sequence key={l.id} from={gStart(l)} layout="none">
                  <AbsoluteFill><ClipMedia fo={fo} id={l.clip!} local={local} grade="saturate(0.9)" /></AbsoluteFill>
                </Sequence>
              ) : null))}
              {full && <ScanAnnotate fo={fo} ann={AN[gLine.clip!]} local={f - Math.max(gStart(gLine), g.open1)} mediaOffset={Math.max(gStart(gLine), g.open1) - gStart(gLine)} outAt={g.end - Math.max(gStart(gLine), g.open1) - 7} />}
              {full && (
                <div style={{ position: "absolute", left: 60, top: 96, display: "flex", alignItems: "center", gap: 12, fontFamily: SANS, color: "#FFF", textShadow: "0 1px 6px rgba(0,0,0,0.5)" }}>
                  <div style={{ width: 28, height: 3, borderRadius: 2, background: PAL.gold, ...shellStyle(f, [-120, 0], 0, g.open1) }} />
                  <FlyText seed={500} start={g.open1 + 2} step={1} style={{ fontWeight: 600, fontSize: 20, letterSpacing: 1, opacity: 0.85 }} runs={[{ s: kicker }]} />
                  <FlyText seed={520} start={g.open1 + 6} step={2} style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 40 }} runs={[{ s: title }]} />
                </div>
              )}
              {full && tag && (
                <div style={{ position: "absolute", left: 100, top: 150, padding: "3px 10px 4px", borderRadius: 6, background: "rgba(20,18,16,0.55)", color: "#FFF", fontFamily: SANS, fontWeight: 600, fontSize: 17, letterSpacing: 1, opacity: seg(f, g.open1 + 8, g.open1 + 14) }}>{tag}</div>
              )}
            </div>
          </div>
        );
      })()}

      {/* ===== cursor + click ripple: same zoom transform as the map, drawn ABOVE the opening clip so press + ripple stay visible ===== */}
      {hub && (
        <AbsoluteFill style={{ transform: `scale(${z})`, transformOrigin: `${O[0]}px ${O[1]}px`, pointerEvents: "none" }}>
          {/* single plain pointer (no name tag) */}
                    {f >= (LINES.find((l) => l.fx === "duet")?.v0 ?? 1e9) && !showA && L.layout !== "END" && (() => {
            const duet = LINES.find((l) => l.fx === "duet")!;
            const lit = seg(f, duet.v0 + 40, duet.v0 + 54, E_IO);
            const appear = seg(f, duet.v0 + 10, duet.v0 + 34, E_OUT);
            const press = cur.ev?.click ? seg(f, cur.ev.f - 2, cur.ev.f + 1) * (1 - seg(f, cur.ev.f + 6, cur.ev.f + 10)) : 0;
            // drawn point (pre-clamp): entrance glide or live target, in the map layer's pre-zoom coordinates
            const px0 = f < duet.v0 + 34 ? lerp(1500, cur.x, appear) : cur.x, py0 = f < duet.v0 + 34 ? lerp(1000, cur.y, appear) : cur.y;
            // while the map PiP is on screen, the point is never drawn inside its expanded rect (clamp in screen space, undo the zoom)
            let x = px0, y = py0;
            if (L.layout === "PIP" && !g) {
              const [sx, sy] = clampOut(O[0] + (px0 - O[0]) * z, O[1] + (py0 - O[1]) * z, MAP_PIP_EXP);
              x = O[0] + (sx - O[0]) / z; y = O[1] + (sy - O[1]) / z;
            }
            return (
              <>
                {cur.ev?.click && <Ripple f={f} click={cur.ev.f} x={x} y={y} color={ACC} z={z} />}
                <NamedCursor x={x} y={y} name="" color={ACC} lit={lit} press={press} o={1 - open} scale={CLICK.cursor / z} />
              </>
            );
          })()}
        </AbsoluteFill>
      )}
      {/* ===== presenter full screen (hard cut; 1.18× punch on the 2nd caption chunk) ===== */}
      {showA && (() => {
        const punch = L.caps.length > 1 && f >= L.caps[1].f0 ? 1.18 : 1;
        return (
          <AbsoluteFill style={{ transform: `scale(${punch})`, transformOrigin: "60% 31%" }}>
            <PresenterClip L={L} f={f} from={aStart(L)} />
          </AbsoluteFill>
        );
      })()}
      {showA && L.big && L.caps[0] && f < (L.caps[1]?.f0 ?? L.f1) && (() => {
        const p = seg(f, L.caps[0].f0, L.caps[0].f0 + 6, E_OUT);
        return (
          <div style={{ position: "absolute", left: 110, top: 360, opacity: p, transform: `scale(${lerp(0.9, 1, p)})`, transformOrigin: "0 100%", fontFamily: NUM, fontStyle: "italic", fontWeight: 800, fontSize: 150, color: PAL.gold, textShadow: "0 0 30px rgba(236,150,60,0.55)", lineHeight: 1 }}>
            {L.big}<span style={{ fontFamily: SANS, fontStyle: "normal", fontWeight: 700, fontSize: 36, marginLeft: 10, color: "#FFF" }}>元/月</span>
            <div style={{ fontFamily: SANS, fontStyle: "normal", fontWeight: 600, fontSize: 20, color: "#FFF", opacity: 0.8, marginTop: 10, letterSpacing: 2 }}>{EP.sampleTag}</div>
          </div>
        );
      })()}
      {showA && L.end && f >= L.caps[L.caps.length - 1].f0 && (
        <div style={{ position: "absolute", left: 100, top: 400, color: "#FFF", fontFamily: TITLE, fontWeight: 700, fontSize: 72, textShadow: "0 2px 12px rgba(0,0,0,0.45)" }}>
          <FlyText seed={700} start={L.caps[L.caps.length - 1].f0} step={2} runs={[{ s: EP.channel }]} />
          <div style={{ fontFamily: NUM, fontStyle: "italic", fontSize: 34, opacity: 0.85, marginTop: 4 }}><FlyText seed={740} start={L.caps[L.caps.length - 1].f0 + 10} step={1} runs={[{ s: EP.episodeTag }]} /></div>
          {NOTES && isHG(L.clip) && <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 20, opacity: seg(f, L.caps[L.caps.length - 1].f0 + 14, L.caps[L.caps.length - 1].f0 + 22), marginTop: 14, letterSpacing: 1, textShadow: "none" }}>出镜为 AI数字人 · 旁白为 AI合成声音 · {EP.sampleTag}</div>}
        </div>
      )}

      {/* footnote (e.g. school line) */}
      {NOTES && L.note && !g && <div style={{ position: "absolute", left: 60, bottom: 196, fontFamily: SANS, fontWeight: 500, fontSize: 16, color: PAL.sub, background: "rgba(251,250,247,0.85)", padding: "3px 10px 4px", borderRadius: 6 }}>{L.note}</div>}


      {/* ===== END: summary panel (shotcraft list-reveal rows + domino-cascade brand row) + avatar small PiP ===== */}
      {f >= END0 && (() => {
        const t0 = END0;
        const rows: [string, string][] = [
          ["户型", `${CHOSEN.layout} · ${CHOSEN.area}㎡ · ${CHOSEN.rent}元/月`],
          ["室内", "整面落地窗 · 人字拼木地板 · 干湿分离"],
          ...PO.filter((p) => ["metro", "school1", "market", "mall", "hospital", "park"].includes(p.id)).map((p) => [({ metro: "地铁", school: "学校", market: "超市", mall: "商场", hospital: "医院", park: "公园" } as Record<string, string>)[p.kind] ?? "", `${p.label} · ${distText(p)}`] as [string, string]),
        ];
        const EL = LINES.find((l) => l.layout === "END" && l.v0 <= f && f < l.v1) ?? LINES.filter((l) => l.layout === "END").pop()!;
        const lastL = LINES[LINES.length - 1];
        return (
          <>
            <AbsoluteFill style={{ background: `rgba(24,21,18,${0.82 * endP})` }} />
            <div style={{ position: "absolute", left: 70, top: 110, width: 900, fontFamily: SANS, color: "#FFF", opacity: endP, transform: `translateY(${lerp(30, 0, endP)}px)` }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
                <FlyText seed={800} start={t0 + 4} step={2} style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 64 }} runs={[{ s: EP.channel }]} />
                <span style={{ fontFamily: NUM, fontStyle: "italic", fontSize: 30, opacity: 0.8 }}>{EP.episodeTag}</span>
              </div>
              <div style={{ marginTop: 8, fontSize: 30, fontWeight: 700, color: PAL.gold }}>{CHOSEN.community}{NOTES && <span style={{ marginLeft: 14, fontSize: 18, fontWeight: 600, padding: "2px 8px 3px", border: "1.5px solid #FFF", borderRadius: 6, color: "#FFF" }}>{EP.sampleTag}</span>}</div>
              <div style={{ marginTop: 22 }}>
                {rows.map(([k, v], i) => {
                  const a = t0 + 14 + i * 5; const q = seg(f, a, a + 9, E_OUT);
                  return (
                    <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 18, padding: "9px 0", borderTop: "1px solid rgba(255,255,255,0.14)", opacity: q, transform: `translateY(${lerp(18, 0, q)}px) scale(${lerp(0.96, 1, q) + 0.015 * Math.sin(Math.min(1, q) * Math.PI)})`, transformOrigin: "0 50%" }}>
                      <span style={{ width: 64, fontSize: 20, fontWeight: 600, color: PAL.gold }}>{k}</span>
                      <span style={{ fontSize: 27, fontWeight: 700 }}>{v}</span>
                    </div>
                  );
                })}
              </div>
              <div style={{ marginTop: 26, fontSize: 16, opacity: 0.75, letterSpacing: 1 }}>{BRANDS.rowLabel}</div>
              <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 24 }}>
                {BRANDS.row.map((b, i) => {
                  const a = t0 + 14 + rows.length * 5 + i * 4; const q = seg(f, a, a + 8, E_OUT);
                  return <div key={b.name} style={{ opacity: q, transform: `translateY(${lerp(-26, 0, q)}px) rotate(${lerp(-8, 0, q)}deg)` }}><Mono file={b.file} ar={b.ar} h={b.h * 1.6} color="#FFFFFF" /></div>;
                })}
              </div>
              {NOTES && <div style={{ marginTop: 26, fontSize: 17, fontWeight: 600, opacity: seg(f, lastL.f0, lastL.f0 + 8) * 0.9 }}>出镜为 AI数字人 · 旁白为 AI合成声音 · 房源为{EP.sampleTag}</div>}
            </div>
            {/* host PiP moved to the upper right so it never covers the in-panel brand row or the bottom brand strip */}
            <div style={{ position: "absolute", right: 64, top: 96, width: 300, height: 220, borderRadius: 16, overflow: "hidden", border: "3px solid #FFFFFF", boxShadow: "0 14px 34px rgba(0,0,0,0.45)", opacity: endP, transform: `scale(${lerp(0.85, 1, endP)})`, transformOrigin: "100% 0%" }}>
              <div style={{ width: W, height: H, transform: `scale(${300 / W})`, transformOrigin: "0 0" }}><PresenterClip L={EL} f={f} from={EL.v0} /></div>
            </div>
            {NOTES && (<AvatarBadge x={W - 64 - 300 + 8} y={96 + 220 + 10} size={15} o={endP} />)}
          </>
        );
      })()}

      {/* captions (non-END) */}
      {cap && f < END0 && <Caption text={cap.text} right={f < OPEN_END && f > 150} size={f < OPEN_END ? 40 : 46} />}
      {/* END caption: left-aligned inside the summary column; box bottom 36px above the brand strip, clear of the upper-right PiP */}
      {cap && f >= END0 && (
        <div style={{ position: "absolute", left: 70, width: 900, bottom: 104, textAlign: "left" }}>
          <span style={{ display: "inline-block", padding: "7px 18px 10px", borderRadius: 10, background: "rgba(18,16,14,0.55)", color: "#FFFFFF", fontFamily: SANS, fontWeight: 700, fontSize: 42, lineHeight: 1.25, letterSpacing: 1 }}>{cap.text}</span>
        </div>
      )}

      {/* chrome: sample-data tag + context credit */}
      <div style={{ position: "absolute", left: 60, top: 54, display: NOTES ? "flex" : "none", gap: 12, alignItems: "center", fontFamily: SANS, color: dark > 0.5 ? "#FFF" : PAL.ink, textShadow: dark > 0.5 ? "0 1px 4px rgba(0,0,0,0.5)" : undefined }}>
        <div style={{ padding: "3px 10px 4px", borderRadius: 6, border: `1.5px solid ${dark > 0.5 ? "#FFF" : PAL.ink}`, opacity: 0.85, fontWeight: 700, fontSize: 15 }}>{EP.sampleTag}</div>
        <div style={{ fontWeight: 500, fontSize: 14, opacity: 0.85 }}>{credit}</div>
      </div>

      <BrandStrip dark={dark} />
    </AbsoluteFill>
  );
};
