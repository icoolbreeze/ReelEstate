// @贝壳-TV map-hub 口播 (series preset "map-hub"): the map is the connective tissue of the whole talk.
//   opener (multiplane → scanline select → dolly zoom) lands on the map → host cursor clicks marks on the map
//   (input-trigger-moves · cursor-performance: bezier glide + wrist flick, hover, press, ripple, punch-in)
//   → the clicked mark opens into its segment (B-roll with scanline-annotate-focus tracking marks) → shrinks back into the mark.
//   L04: a single plain cursor glides in (no name tags).
// Everything is data: src/episode/{timeline,hub,pois,footage,annotations,episode,listings,brands}.json (see pipeline/).
import { MarkerUnderline } from "./components/MarkerUnderline";
import React from "react";
import { AbsoluteFill, Audio, Freeze, Img, Sequence, staticFile, useCurrentFrame, getInputProps, Loop } from "remotion";
import { NUM, SANS, TITLE } from "./fonts";
import TL from "./episode/timeline.json";
import HUB from "./episode/hub.json";
import POIS from "./episode/pois.json";
import FOOT from "./episode/footage.json";
import ANNS from "./episode/annotations.json";
import EP from "./episode/episode.json";
import DATA from "./episode/listings.json";
import { OPENER_NOTES, Opener, camAt, proj, Cam, TY, ROUTE, T as TO } from "./components/opener/Opener";
import { FlyText, landsAt, shellStyle } from "./components/opener/TypeFly";
import { BakedBadge, BakedFocusCard, BakedPinChip, BakedRoomChip } from "./bakedLabel";
import { planLeader, pickLeaderReference, leaderPathJump, rectanglePorts, type Obstacle } from "./leaderRouting";
import { BrandStrip } from "./components/BrandStrip";
import { Mono } from "./components/opener/Opener";
import BRANDS from "./episode/brands.json";
import { ClipMedia, ScanAnnotate, Footage, Ann } from "./components/ScanAnnotate";
import { Space3DClips, Space3DSpec } from "./components/Space3DClips";
import { NamedCursor, Ripple, bez } from "./components/Cursor";
import { E_IO, E_OUT, FULL, H, PAL, Rect, W, lerp, lerpRect, seg, TEMPO, spring } from "./lib";
import { buildTrack, cardLensScale, evalTrack, mergeMoveStarts, overlayTransform, type CamSeg } from "./mapMotion";

type Cap = { text: string; f0: number; f1: number };
type Insert = { clip: string; mark: string; f0: number; f1: number; click: number };
type Line = { id: string; insert?: Insert; layout: "OPENER" | "A" | "PIP" | "MAP" | "B" | "END"; clip?: string; cam?: string; enter?: string; poi?: string[]; f0: number; f1: number; v0: number; v1: number; caps: Cap[]; click?: number; note?: string; big?: string; end?: boolean; fx?: string; pip?: string; pipPos?: "br" | "bl"; hold_f?: number };
type Poi = { id: string; kind: string; label: string; sub: string; xy: number[]; walking_m?: number; driving_m?: number; walk_path?: number[][]; drive_path?: number[][] };
const LINES = TL.lines as unknown as Line[];
export const TOTAL = TL.total as number;
const OPEN_END = TL.opener as number;
// onScreenNotes=false (episode.json): only the bottom brand strip stays — no AI示意 / 示例数据 / AI数字人 / disclaimer labels
export const NOTES = (EP as any).onScreenNotes !== false;
OPENER_NOTES.on = NOTES;           // 240
const CAMS = HUB.cams as Record<string, Cam>;
const PO = POIS.pois as unknown as Poi[];
// optional community boundary (episode pois.json `aoi`: { pts: plane xy[], gate_xy }) - drawn on the hub plane under the routes
const AOI = (POIS as any).aoi as { pts: number[][]; gate_xy?: number[] } | undefined;
const AOI_PTS = AOI?.pts ?? null;
// optional per-POI area boundary (pois.json pois[].aoi: plane xy[]): outlined + lightly filled when a line first mentions that POI (line.poi), held after
const POI_AOI = (POIS.pois as any[]).filter((p) => Array.isArray(p.aoi) && p.aoi.length > 2).map((p) => ({ id: p.id as string, pts: p.aoi as number[][], credit: (p.aoi_credit as string | undefined), f0: (LINES.find((l: any) => (l.poi ?? []).includes(p.id))?.f0 ?? 1e9) as number }));
const FO = FOOT as unknown as Record<string, Footage>;
const AN = ANNS as unknown as Record<string, Ann>;
const LST = POIS.listing.xy as number[];
const CHOSEN = (DATA.mid as any[]).find((l) => l.id === DATA.chosenId);
const ACC = PAL.accent;
const ROOM_PREFIX = (EP as any).sampleData === true ? "示例房源" : "";
const CLEAN_END = (EP as any).presentation?.ending === "clean";
const FOCUS_ROOMS = (EP as any).presentation?.roomCards === "focus";

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
  const end = LINES[j].f1 + 4 + ((LINES[j] as any).hold_f ?? 0);   // optional hold keeps the B-roll open after the last word
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

const glyphCount = (s: string) => Array.from(s).length;
/** Last frame of a FlyText run. The next frame is one static string. */
const flyEnd = (start: number, text: string, step: number) => {
  const n = glyphCount(text);
  return n <= 0 ? start : landsAt(start, n, step);
};
export const companionFlyEnd = (open1: number, kicker: string, title: string) =>
  Math.max(flyEnd(open1 + 2, kicker, 1), flyEnd(open1 + 6, title, 2));
export const poiLabelFlyEnd = (start: number, text: string) => flyEnd(start, text, 1);
export const companionPhase = (f: number, open1: number, kicker: string, title: string): "off" | "fly" | "static" => {
  if (f < open1) return "off";
  return f > companionFlyEnd(open1, kicker, title) ? "static" : "fly";
};
const kickerFor = (mark: string) =>
  HUB.rooms.some((r) => r.id === mark) ? ROOM_PREFIX
    : mark === HUB.env.id ? (NOTES ? "小区环境 · AI示意" : "小区环境") : "周边配套";
const clipTitleFor = (mark: string, clip?: string) =>
  ((HUB as { clipTitles?: Record<string, string> }).clipTitles?.[clip ?? ""] ??
    HUB.rooms.find((r) => r.id === mark)?.label ??
    (mark === HUB.env.id ? HUB.env.label : PO.find((p) => p.id === mark)?.label ?? ""));
const companionCopy = (g: Group) => {
  let title = "";
  for (const l of g.lines) {
    const t = clipTitleFor(g.mark, l.clip);
    if (glyphCount(t) > glyphCount(title)) title = t;
  }
  return { kicker: kickerFor(g.mark), title };
};
const inCompanionFly = (f: number) => GROUPS.some((g) => {
  const copy = companionCopy(g);
  return f >= g.open1 && f <= companionFlyEnd(g.open1, copy.kicker, copy.title);
});
// first frame of the END summary panel (hoisted so caption placement can reuse it)
const END0 = LINES.find((l) => l.layout === "END")?.v0 ?? 1e9;
// optional basic-3d-scene (hub.json "space3d"): anchors {line, t} resolve to line.f0 + t s, so a voice retime keeps it in sync
const SPACE3D: Space3DSpec | null = (() => {
  const C = (HUB as any).space3d; if (!C) return null;
  const at = (a: { line: string; t: number }) => { const l = LINES.find((x) => x.id === a.line); return l ? Math.round(l.f0 + a.t * 30) : 1e9; };
  return { f0: at(C.start), f1: at(C.end), fly: C.fly, stations: C.stations.map((st: any) => ({ ...st, arrive: at(st.arrive) })), overview: { ...C.overview, arrive: at(C.overview.arrive) } };
})();
const lineAt = (f: number) => { let r = LINES[0]; for (const l of LINES) if (l.v0 <= f) r = l; return r; };
const prevGroupClose = (L: Line) => { const g = GROUPS.filter((g) => g.close1 <= L.f0 + 1).pop(); return g ? g.close1 : -1; };
const aStart = (L: Line) => Math.max(L.v0, prevGroupClose(L));

// ---------- camera track ----------
// Knot frame is when a move STARTS. The pose at OPEN_END is the settled opener camera.
// Push during a hold is inside this track (ramps in and out). It is not a second term on the ease.
const HOME = { f: OPEN_END, cam: camAt(OPEN_END - 1) };
const RAW_MOVES: { f: number; cam: Cam }[] = [];
for (const L of LINES) {
  if ((L.layout === "PIP" || L.layout === "MAP") && L.cam) RAW_MOVES.push({ f: Math.max(L.v0, prevGroupClose(L) - 12), cam: CAMS[L.cam] });
  if (L.enter && L.click !== undefined) RAW_MOVES.push({ f: L.click - 30, cam: CAMS[(HUB.enterCam as Record<string, string>)[L.enter]] ?? CAMS.community });
}
const MOVES = mergeMoveStarts(HOME.f, RAW_MOVES);
export const MOTION_SEGS: CamSeg[] = buildTrack(HOME, MOVES);
export const camHub = (f: number): Cam => (f < OPEN_END ? camAt(f) : evalTrack(HOME, MOTION_SEGS, f));

// ---------- marks ----------
const HEAD = 88, HOFF = { x: 82, y: -58 };
// Seed only. The opener collision layout is built from this once, at the settled camera.
// Runtime clicks and cards use markCenter / markRect further down, which follow that layout.
const roomKSeed = (c: Cam) => Math.min(1.05, Math.max(0.5, c.s / 2));
const CARD = { w: 150, h: 112 };
const seedCenter = (id: string, c: Cam): number[] => {
  const G = proj(c, LST[0], LST[1]);
  const room = HUB.rooms.find((r) => r.id === id);
  if (room) { const k = roomKSeed(c); return [G.x + HOFF.x + room.off[0] * k + (CARD.w * k) / 2, G.y + HOFF.y + room.off[1] * k + (CARD.h * k) / 2]; }
  if (id === HUB.env.id) { const p = proj(c, LST[0] + HUB.env.dxy[0], LST[1] + HUB.env.dxy[1]); return [p.x, p.y]; }
  const poi = PO.find((p) => p.id === id);
  if (poi) { const p = proj(c, poi.xy[0], poi.xy[1]); return [p.x, p.y]; }
  return [W / 2, H / 2];
};

// ---------- click punch-in (map layer scales about the click point; cursor lives on the same layer) ----------
const zoomAt = (f: number) => {
  // push-in toward the target during the glide/pause, hold through the press, a little more while the clip opens, ease back on return
  const LEADF = CLICK.glide + CLICK.pause;
  const g = GROUPS.find((q) => f >= q.click - LEADF && f < q.close1);
  if (!g) return { z: 1, O: [W / 2, H / 2] };
  const zp = CLICK.pushZ, zo = CLICK.pushZ * 1.08;
  const z = f < g.click ? lerp(1, zp, seg(f, g.click - LEADF, g.click - 3, E_IO)) : f < g.end ? lerp(zp, zo, seg(f, OPEN_A(g.click), g.open1, E_IO)) : lerp(zo, 1, seg(f, g.end, g.close1, E_IO));
  // Origin tracks this frame's mark while the punch is active, so a moving camera cannot whip a frozen origin.
  const O = z === 1 ? [W / 2, H / 2] : markCenter(g.mark, camHub(f));
  return { z, O };
};
const zoomRect = (r: Rect, z: number, O: number[]): Rect => ({ x: O[0] + (r.x - O[0]) * z, y: O[1] + (r.y - O[1]) * z, w: r.w * z, h: r.h * z });

// map PiP exclusion zone in SCREEN space: while that PiP is on screen the cursor must never be drawn inside it.
// PiP is right:50 / bottom:190 / 330×248. The NamedCursor tip sits at the anchor point but its 44px glyph renders at
// CLICK.cursor=1.7×, reaching ~69px right / ~72px down from the tip (svg offsets -3.2 / -1.6), so the rect must be
// expanded by the glyph extents plus 16px — then the *visible pointer* (not just the tip) clears the PiP border.
const PIP_R: Rect = { x: W - 50 - 330, y: H - 190 - 248, w: 330, h: 248 };
const PIP_GAP = 16;
// PiP exceptions: only where the default rect would cover key info (caption, rent, labels, tracked boxes, route/markers); move minimally.
const PIP_EXCEPT: Record<string, { x: number; y: number; why: string }> = {};
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
  hotel: '<path d="M3 18V7"/><path d="M3 14h18v4"/><path d="M21 14v-2a3 3 0 0 0-3-3h-7v5"/><circle cx="7" cy="11" r="2"/>',
  bus: '<rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 10h14"/><circle cx="8.5" cy="13.5" r="1"/><circle cx="15.5" cy="13.5" r="1"/><path d="M7 17v3M17 17v3"/>',
  env: '<path d="M5 19c0-8 6-14 14-14 0 8-6 14-14 14z"/><path d="M5 19l8-8"/>',
};
const Icon: React.FC<{ k: string; size?: number; color?: string }> = ({ k, size = 24, color = PAL.ink }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: ICON[k] ?? ICON.env }} />
);
const distText = (p: Poi) => (p.kind === "hospital" && p.driving_m ? `驾车约 ${(p.driving_m / 1000).toFixed(1)} 公里`
  : (p.walking_m ?? 0) >= 1000 ? `步行约 ${((p.walking_m ?? 0) / 1000).toFixed(1)} 公里` : `步行 ${p.walking_m} 米`);

// ---------- map plane (same CSS camera as the opener's MapPlane) ----------
type PathDef = { d: number[][]; p: number; color: string; w: number; o: number; flow?: number };
// one shared builder: the map image, route <svg>, all markers and the cursor use the exact same transform
const camTransform = (c: Cam) => `translate3d(${720 - c.fx}px, ${540 + TY - c.fy}px, 0) rotateX(${c.tilt}deg) scale(${c.s})`;
const HubPlane: React.FC<{ c: Cam; paths: PathDef[]; aoiP?: number; poiAoi?: { pts: number[][]; p: number }[]; children?: React.ReactNode }> = ({ c, paths, aoiP = 0, poiAoi = [], children }) => {
  const ext = EP.mapBase.ext;
  return (
    <div data-harmony-world="map" data-world-source={EP.mapBase.file} style={{ position: "absolute", inset: 0, perspective: c.P, perspectiveOrigin: "720px 540px" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1440, height: 1080, transformOrigin: `${c.fx}px ${c.fy}px`, transform: camTransform(c) }}>
        <Img src={staticFile(EP.mapBase.file)} style={{ position: "absolute", left: ext[0], top: ext[1], width: ext[2] - ext[0], height: ext[3] - ext[1] }} />
        <svg width={1440} height={1080} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
          {AOI_PTS && aoiP > 0.001 && (() => {
            const d = AOI_PTS.map((p, k) => `${k ? "L" : "M"}${p[0]} ${p[1]}`).join(" ") + " Z";
            const sw = 3 / Math.max(0.6, c.s / 1.6);
            return (
              <g>
                <path d={d} fill={ACC} fillOpacity={0.14 * seg(aoiP, 0.55, 1)} stroke="none" />
                <path d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.9} strokeWidth={sw + 3} strokeLinejoin="round" pathLength={1} strokeDasharray={`${aoiP} 2`} />
                <path d={d} fill="none" stroke={ACC} strokeWidth={sw} strokeLinejoin="round" pathLength={1} strokeDasharray={`${aoiP} 2`} />
                {AOI?.gate_xy && aoiP > 0.95 && <circle cx={AOI.gate_xy[0]} cy={AOI.gate_xy[1]} r={5 / Math.max(0.6, c.s / 1.6)} fill="#FFFFFF" stroke={ACC} strokeWidth={sw} />}
              </g>
            );
          })()}
          {poiAoi.filter((a) => a.p > 0.001).map((a, i) => {
            const d = a.pts.map((p, k) => `${k ? "L" : "M"}${p[0]} ${p[1]}`).join(" ") + " Z";
            const sw = 2.5 / Math.max(0.6, c.s / 1.6);
            return (
              <g key={"pa" + i}>
                <path d={d} fill={ACC} fillOpacity={0.12 * seg(a.p, 0.55, 1)} stroke="none" />
                <path d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.9} strokeWidth={sw + 3} strokeLinejoin="round" pathLength={1} strokeDasharray={`${a.p} 2`} />
                <path d={d} fill="none" stroke={ACC} strokeWidth={sw} strokeLinejoin="round" pathLength={1} strokeDasharray={`${a.p} 2`} />
              </g>
            );
          })}
          {paths.filter((q) => q.p > 0.001).map((q, i) => {
            const d = q.d.map((p, k) => `${k ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");
            return (
              <g key={i} opacity={q.o}>
                <path d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.95} strokeWidth={(q.w + 6.5) / Math.max(0.6, c.s / 1.6)} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${q.p} 2`} />
                <path d={d} fill="none" stroke={q.color} strokeWidth={q.w / Math.max(0.6, c.s / 1.6)} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={`${q.p} 2`} />
                {q.flow !== undefined && q.p >= 0.999 && <path d={d} fill="none" stroke="#FFFFFF" strokeOpacity={0.85} strokeWidth={(q.w * 0.42) / Math.max(0.6, c.s / 1.6)} strokeLinecap="round" pathLength={1} strokeDasharray="0.012 0.028" strokeDashoffset={-q.flow * 0.0025} />}
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
const poiDim = (f: number): Record<string, number> => {
  const dim: Record<string, number> = {};
  for (const p of PO) {
    const cur = focusSpans(p.id).find((s) => f >= s.a && f < s.b);
    dim[p.id] = cur ? seg(f, cur.a, cur.a + 8, E_OUT) * (1 - seg(f, cur.b - 6, cur.b)) : 0;
  }
  return dim;
};
// Hub-only extras: focus photo / line badges / expanded POI copy, plus the listing ground dot and photo head.
// Room cards, the env badge, resting POI badges, and their leaders live in PlacedMarks (one geometry across the cut).
const Marks: React.FC<{ f: number; c: Cam; z: number; O: number[]; hot?: string; press?: number }> = ({ f, c, z, O, hot, press = 0 }) => {
  const G = proj(c, LST[0], LST[1]);
  const hx = G.x + HOFF.x, hy = G.y + HOFF.y;
  const INSET = 48;
  const punching = z > 1.05;
  const labelKept = (b: { x: number; y: number; w: number; h: number }) => {
    if (!punching) return true;
    const sx = O[0] + (b.x - O[0]) * z, sy = O[1] + (b.y - O[1]) * z;
    return sx >= INSET && sy >= INSET && sx + b.w * z <= W - INSET && sy + b.h * z <= H - INSET;
  };
  return (
    <>
      {PO.map((p, i) => {
        const ft = REVEAL.pois + i * 4;
        if (f < ft) return null;
        const q = proj(c, p.xy[0], p.xy[1]);
        if (q.x < -100 || q.x > W + 100 || q.y < -100 || q.y > H + 60) return null;
        const spans = focusSpans(p.id);
        const cur = spans.find((s) => f >= s.a && f < s.b);
        const seen = spans.some((s) => f >= s.b);
        const lo = cur ? seg(f, cur.a, cur.a + 8, E_OUT) * (1 - seg(f, cur.b - 6, cur.b)) : 0;
        const laid = OPENER_LAYOUT.some((it) => it.id === p.id);
        // Resting badge is PlacedMarks. This layer draws the focus card, and a pin only when no layout badge exists.
        if (laid && lo <= 0 && !cur) return null;
        const r = 24 * (cur ? 1.12 : 0.92) * (hot === p.id ? 1.08 - 0.1 * press : 1);
        const labelBox = lo > 0
          ? { x: q.x + r + 10, y: q.y - 34, w: Math.max(p.label.length * 22, p.sub.length * 15 + 8 + distText(p).length * 18) + 28, h: 86 }
          : { x: q.x + r + 10, y: q.y - 15, w: p.label.length * 14 + 18, h: 21 };
        const showLabel = f >= ft + 6 && (lo > 0 || !laid) && labelKept(labelBox);
        return (
          <React.Fragment key={p.id}>
            <div style={{ position: "absolute", left: 0, top: 0, transform: overlayTransform(q.x, q.y) }}>
              {cur && (() => { const ph = ((f - cur.a) % 30) / 30; const rr = r * lerp(1, 2.5, ph); return <div style={{ position: "absolute", left: -rr, top: -rr, width: 2 * rr, height: 2 * rr, borderRadius: rr, border: `3px solid ${ACC}`, opacity: 0.55 * (1 - ph) * seg(f, cur.a, cur.a + TEMPO.enter) }} />; })()}
              {cur && (p as any).photo && (() => {
                const a0 = cur.a + 10, ks = spring(f, a0), out = 1 - seg(f, cur.b - TEMPO.exit, cur.b);
                if (f < a0) return null;
                const pw = 220, phh = 165;
                return <div style={{ position: "absolute", left: -pw / 2, top: -r - phh - 22, width: pw, height: phh, padding: 6, background: "#FFFFFF", borderRadius: 10, boxSizing: "border-box", boxShadow: "0 14px 30px rgba(38,32,24,0.30)", opacity: ks.o * out, transform: `translateY(${lerp(phh * 0.5, 0, ks.p)}px) scale(${ks.p * (1 + 0.12 * ks.sq)}, ${ks.p * (1 - 0.12 * ks.sq)})`, transformOrigin: "50% 100%" }}>
                  <Img src={staticFile((p as any).photo)} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: 6, display: "block" }} />
                  <span style={{ position: "absolute", right: 10, bottom: 8, fontFamily: SANS, fontSize: 10, color: "rgba(255,255,255,0.85)", textShadow: "0 1px 2px rgba(0,0,0,0.6)" }}>Wikimedia Commons</span>
                </div>;
              })()}
              {cur && (() => {
                const toks: string[] = (p.sub.match(/\d+号线|K\d+/g) ?? []);
                if (!toks.length) return null;
                const Lc = lineAt(f); const cp = Lc.caps.find((c0) => toks.some((t) => c0.text.includes(t))); const a0 = cp ? cp.f0 : cur.a + 12;
                return <div style={{ position: "absolute", left: r + 10, top: 60, display: "flex", gap: 8 }}>
                  {toks.map((t, ti) => { const ks = spring(f, a0 + ti * TEMPO.stagger); return <div key={t} style={{ opacity: ks.o * (1 - seg(f, cur.b - TEMPO.exit, cur.b)), transform: `scale(${ks.p})`, transformOrigin: "0 50%" }}><BakedBadge text={t} options={{ fontPx: 20, weight: 800, color: "#FFF", radius: 8, background: p.kind === "metro" ? (t.startsWith("4") ? "#2E9E4F" : "#E5A33B") : "#7B2FF7" }} /></div>; })}
                </div>;
              })()}
              {!laid && (
                <div style={{ position: "absolute", left: -r, top: -r, width: 2 * r, height: 2 * r }}>
                  <div style={{ width: "100%", height: "100%", borderRadius: r, background: cur ? PAL.ink : PAL.card, border: `1px solid ${PAL.border}`, boxShadow: PAL.shadow, display: "flex", alignItems: "center", justifyContent: "center", ...shellStyle(f, [((i % 3) - 1) * 90, -110], ((i % 2) * 2 - 1) * 6, ft) }}>
                    <Icon k={p.kind} size={24} color={cur ? "#FFF" : PAL.ink} />
                  </div>
                </div>
              )}
              {showLabel && (
                <div data-map-focus={p.id} style={{ position: "absolute", left: 0, top: 0, transform: overlayTransform(r + 10, -(lo > 0 ? 34 : 15)), opacity: lo > 0 ? seg(f, cur!.a, cur!.a + 8, E_OUT) : 0.85 * seg(f, ft + 6, ft + 14) * (seen || p.kind === "metro" || cur ? 1 : 0.9) }}>
                  {lo > 0 ? (
                    <BakedFocusCard
                      title={p.label}
                      detail={p.sub}
                      reserveDistance={distText(p)}
                      distance={distText(p).replace(/\d+(\.\d+)?/, (m) => {
                        const v = parseFloat(m), u = seg(f, cur!.a + 4, cur!.a + 4 + 2 * TEMPO.move, E_OUT);
                        return m.includes(".") ? (v * u).toFixed(1) : String(Math.round(v * u));
                      })}
                    />
                  ) : <BakedBadge text={p.label} options={{ fontPx: 14, weight: 600, padX: 8, padT: 2, padB: 3, background: "rgba(251,250,247,0.82)" }} shadow={false} />}
                </div>
              )}
            </div>
          </React.Fragment>
        );
      })}
      <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0 }}>
        <ellipse cx={G.x} cy={G.y} rx={8} ry={4.5} fill={ACC} stroke={PAL.ink} strokeWidth={1.5} />
      </svg>
      <div style={{ position: "absolute", left: 0, top: 0, width: HEAD, height: HEAD, borderRadius: HEAD / 2, overflow: "hidden", boxShadow: "0 0 0 4px #FFFFFF, 0 10px 24px rgba(31,28,23,0.35)", transform: overlayTransform(hx - HEAD / 2, hy - HEAD / 2) }}>
        <Img src={staticFile(`photos_g/${CHOSEN.photo}`)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
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
export type LabelMode = "screen-fixed" | "scaled-dom" | "baked";
export type LabelPlan = {
  inLensScale: boolean;
  fontPx: number;
  motion: "translate" | "lens-scale" | "image-scale";
  rasterScale?: number;
  liveDomText?: boolean;
};
/** How a mark's words are drawn. Screen-fixed text is not inside the lens scale. */
export const labelTextPlan = (mode: LabelMode, kind: "room" | "poi" | "env"): LabelPlan => {
  const fontPx = kind === "room" ? 24 : OM.font;
  if (mode === "screen-fixed") return { inLensScale: false, fontPx, motion: "translate", rasterScale: 3, liveDomText: false };
  if (mode === "baked") return { inLensScale: true, fontPx, motion: "image-scale", rasterScale: 3, liveDomText: false };
  return { inLensScale: true, fontPx, motion: "lens-scale", liveDomText: true };
};
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
  HUB.rooms.forEach((r, i) => { const [x, y] = seedCenter(r.id, c); items.push({ id: r.id, kind: "room", label: r.label, ax: head.x, ay: head.y, box: { x: x - OM.card.w / 2, y: y - OM.card.h / 2 - 30, w: OM.card.w, h: OM.card.h + OM.cardLabel }, order: i, photo: FO[(r as any).clip]?.still ?? r.photo }); });
  const pw = (t: string) => OM.pin + 12 + t.length * OM.font + 26;
  { const [x, y] = seedCenter(HUB.env.id, c); items.push({ id: HUB.env.id, kind: "env", label: HUB.env.label, ax: x, ay: y, box: { x: x - OM.pin / 2, y: y - OM.pin / 2, w: pw(HUB.env.label), h: OM.pin }, order: 3 }); }
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
  // Plan badge offsets over the initial map move, not independently per frame.
  // This prevents a badge entering a shrinking room photo after the opener.
  const stop = Math.min(POI_PART, GROUPS[0]?.click ?? OPEN_END + 90);
  const poses = Array.from({ length: 9 }, (_, i) => camHub(lerp(OPEN_END, stop, i / 8)));
  const projected = (item: OItem, cam: Cam, dx = 0, dy = 0) => {
    const point = item.kind === "room" ? LST : item.kind === "env" ? [LST[0] + HUB.env.dxy[0], LST[1] + HUB.env.dxy[1]] : PO.find((p) => p.id === item.id)!.xy;
    const q = proj(cam, point[0], point[1]), lens = cardLensScale(cam.s);
    return { x: item.box.x + dx + q.x + (item.kind === "room" ? HOFF.x : 0) - item.ax, y: item.box.y + dy + q.y + (item.kind === "room" ? HOFF.y : 0) - item.ay, w: item.box.w * lens, h: item.box.h * lens };
  };
  const offsets = [[0,0], [0,-48], [0,-72], [0,-96], [-72,0], [72,0], [-96,-48], [96,-48], [0,48]];
  for (const item of items.filter((it) => it.kind !== "room")) {
    let best = [0,0], cost = Infinity;
    for (const [dx,dy] of offsets) {
      let score = Math.hypot(dx,dy);
      for (const cam of poses) {
        const candidate = projected(item,cam,dx,dy);
        score += items.filter((it) => it.kind === "room").filter((it) => hit(candidate,projected(it,cam),8)).length * 10000;
        if (candidate.y < 96 || candidate.y + candidate.h > 910 || candidate.x < 24 || candidate.x + candidate.w > W - 24) score += 10000;
      }
      for (const other of items) if (other !== item && other.kind !== "room" && hit({ ...item.box, x:item.box.x+dx,y:item.box.y+dy },other.box,8)) score += 10000;
      if (score < cost) { cost = score; best = [dx,dy]; }
    }
    item.box = { ...item.box, x:item.box.x+best[0], y:item.box.y+best[1] };
  }
  return items;
})();

const SETTLE_CAM = camAt(OPEN_END - 1);
const anchorOf = (it: OItem, c: Cam) => {
  if (it.kind === "poi") {
    const p = PO.find((q) => q.id === it.id);
    const q = proj(c, p ? p.xy[0] : LST[0], p ? p.xy[1] : LST[1]);
    return { x: q.x, y: q.y };
  }
  if (it.kind === "env") {
    const q = proj(c, LST[0] + HUB.env.dxy[0], LST[1] + HUB.env.dxy[1]);
    return { x: q.x, y: q.y };
  }
  const G = proj(c, LST[0], LST[1]);
  return { x: G.x + HOFF.x, y: G.y + HOFF.y };
};
/** Opener collision box, shifted by how far its geographic anchor has moved. Label offset stays in screen pixels. */
const boxNow = (it: OItem, c: Cam): OBox => {
  const a0 = anchorOf(it, SETTLE_CAM);
  const a1 = anchorOf(it, c);
  return { x: it.box.x + (a1.x - a0.x), y: it.box.y + (a1.y - a0.y), w: it.box.w, h: it.box.h };
};
const markCenter = (id: string, c: Cam): number[] => {
  const it = OPENER_LAYOUT.find((q) => q.id === id);
  if (!it) return seedCenter(id, c);
  const b = boxNow(it, c);
  const lens = cardLensScale(c.s);
  if (it.kind === "room") return [b.x + (OM.card.w * lens) / 2, b.y + (OM.card.h * lens) / 2];
  return [b.x + (OM.pin * lens) / 2, b.y + (OM.pin * lens) / 2];
};
const markRect = (id: string, c: Cam): Rect => {
  const it = OPENER_LAYOUT.find((q) => q.id === id);
  if (it?.kind === "room") {
    const b = boxNow(it, c);
    const lens = cardLensScale(c.s);
    return { x: b.x, y: b.y, w: OM.card.w * lens, h: OM.card.h * lens };
  }
  const [x, y] = markCenter(id, c);
  return { x: x - 36, y: y - 27, w: 72, h: 54 };
};
export const auditLayout = (f: number) => {
  const c = camHub(f);
  const draw = f < OPEN_END ? SETTLE_CAM : c;
  const marks = OPENER_LAYOUT.map((it) => {
    const b = boxNow(it, draw);
    const a = anchorOf(it, draw);
    const lens = cardLensScale(draw.s);
    const poi = it.kind === "poi" ? PO.find((p) => p.id === it.id) : undefined;
    const geo = it.kind === "poi"
      ? proj(draw, poi ? poi.xy[0] : 0, poi ? poi.xy[1] : 0)
      : it.kind === "env"
        ? proj(draw, LST[0] + HUB.env.dxy[0], LST[1] + HUB.env.dxy[1])
        : proj(draw, LST[0], LST[1]);
    return {
      id: it.id, kind: it.kind, x: b.x, y: b.y,
      w: it.kind === "room" ? OM.card.w : b.w, h: it.kind === "room" ? OM.card.h : b.h,
      lens, ax: a.x, ay: a.y, gx: geo.x, gy: geo.y,
    };
  });
  return { f, cam: c, marks };
};


const guideGeometry = (c: Cam, f: number) => {
  const lens = cardLensScale(c.s);
  const G = proj(c, LST[0], LST[1]);
  const hx = G.x + HOFF.x, hy = G.y + HOFF.y;
  const pad = 7;
  const obstacles: Obstacle[] = [
    { id: "head", kind: "circle", x: hx, y: hy, r: HEAD / 2 + pad },
    { id: "caption", kind: "rect", x: 0, y: H - 216, w: W, h: 216 },
    { id: "chrome", kind: "rect", x: 0, y: 0, w: W, h: 88 },
    { id: "presenter", kind: "rect", x: PIP_R.x - 8, y: PIP_R.y - 8, w: PIP_R.w + 16, h: PIP_R.h + 16 },
  ];
  const entries: { id: string; kind: string; anchor: { x: number; y: number }; ports: { x: number; y: number }[]; needed: boolean }[] = OPENER_LAYOUT.map((it) => {
    const b = boxNow(it, c), anchor = anchorOf(it, c);
    const body = { x: b.x, y: b.y, w: (it.kind === "room" ? OM.card.w : OM.pin) * lens, h: (it.kind === "room" ? OM.card.h : OM.pin) * lens };
    const badgeVisible = it.kind !== "poi" ? f < POI_PART + 8 : (poiDim(f)[it.id] ?? 0) < 0.98;
    if (badgeVisible && it.kind === "room") obstacles.push({ id: it.id + ":body", kind: "rect", x: body.x - pad, y: body.y - pad, w: body.w + 2 * pad, h: body.h + 2 * pad });
    else if (badgeVisible) obstacles.push({ id: it.id + ":body", kind: "circle", x: body.x + body.w / 2, y: body.y + body.h / 2, r: body.w / 2 + pad });
    const wordsW = it.kind === "room"
      ? (24 + Array.from(it.label).length * 24 + (ROOM_PREFIX ? Array.from(ROOM_PREFIX).length * 20 + 6 : 0)) * lens
      : (24 + Array.from(it.label).length * OM.font) * lens;
    const wordsH = (it.kind === "room" ? 37 : 42.5) * lens;
    const label = it.kind === "room"
      ? { x: b.x + (OM.card.w * lens - wordsW) / 2, y: b.y + (OM.card.h + 8) * lens, w: wordsW, h: wordsH }
      : { x: b.x + (OM.pin + 8) * lens, y: b.y + (OM.pin * lens - wordsH) / 2, w: wordsW, h: wordsH };
    if (badgeVisible) obstacles.push({ id: it.id + ":words", kind: "rect", x: label.x - 4, y: label.y - 4, w: label.w + 8, h: label.h + 8 });
    return { id: it.id, kind: it.kind, anchor, ports: rectanglePorts(body, pad), needed: badgeVisible && (it.kind === "room" || Math.hypot(body.x + body.w/2 - anchor.x, body.y + body.h/2 - anchor.y) > 34) };
  });
  for (const p of PO) {
    const span = focusSpans(p.id).find((s) => f >= s.a && f < s.b);
    if (!span) continue;
    const q = proj(c, p.xy[0], p.xy[1]);
    const w = Math.max(p.label.length * 22, p.sub.length * 15 + 8 + distText(p).length * 18) + 28;
    obstacles.push({ id: p.id + ":focus", kind: "rect", x: q.x + 32, y: q.y - 40, w: w + 12, h: 98 });
  }
  entries.push({ id: "listing", kind: "listing", needed: true, anchor: { x: G.x, y: G.y }, ports: rectanglePorts({ x: hx - HEAD / 2, y: hy - HEAD / 2, w: HEAD, h: HEAD }, pad) });
  return { obstacles, entries };
};
const GUIDE_REFERENCE = (() => {
  const stop = Math.min(POI_PART, GROUPS[0]?.click ?? OPEN_END + 90);
  const count = Math.max(2,Math.ceil((stop-OPEN_END)/4)+1);
  const scenes = Array.from({length:count},(_,i)=> {
    const f = lerp(OPEN_END,stop,i/(count-1));
    return guideGeometry(camHub(f),f);
  });
  const g = guideGeometry(SETTLE_CAM, OPEN_END);
  return new Map(g.entries.map((e) => {
    let preferred = pickLeaderReference(scenes.map((s)=>{
      const entry=s.entries.find((q)=>q.id===e.id)!;
      return {anchor:entry.anchor,ports:entry.ports,obstacles:s.obstacles};
    }));
    const head = g.obstacles.find((o) => o.id === "head")!;
    if (e.kind === "poi" && e.ports[0].y > head.y)
      preferred = { points: [], nodes: ["start","head:4","head:3","head:2","port:0"], port: 0, clear: true };
    return [e.id,preferred];
  }));
})();
const leaderFade = (id: string, f: number) => focusSpans(id).reduce((o,s)=>
  o * (1-seg(f,s.a-4,s.a)*(1-seg(f,s.b,s.b+4))),1);

const rawGuidePlans = (c: Cam, f: number) => {
  const g = guideGeometry(c, f);
  return { obstacles: g.obstacles, plans: g.entries.map((e) => ({ id: e.id, kind: e.kind, anchor: e.anchor, needed: e.needed, ...(e.needed ? planLeader(e.anchor, e.ports, g.obstacles, GUIDE_REFERENCE.get(e.id)) : { points: [], nodes: [], port: 0, clear: true }) })) };
};
const guidePlanCache = new Map<number,ReturnType<typeof rawGuidePlans>>();
const cachedGuidePlans = (f: number, c?: Cam) => {
  const hit=guidePlanCache.get(f);
  if(hit)return hit;
  const result=rawGuidePlans(c ?? (f<OPEN_END?SETTLE_CAM:camHub(f)),f);
  guidePlanCache.set(f,result);
  return result;
};
const routeJumpCache = new Map<number,Set<string>>();
const routeJumps = (f:number) => {
  const hit=routeJumpCache.get(f);if(hit)return hit;
  const before=cachedGuidePlans(f-1).plans,current=cachedGuidePlans(f).plans;
  const jumps=new Set(current.filter((p)=>p.needed && leaderPathJump(before.find((a)=>a.id===p.id)!,p)).map((p)=>p.id));
  routeJumpCache.set(f,jumps);return jumps;
};
const guidePlans = (c:Cam,f:number) => {
  const raw=cachedGuidePlans(f,c);
  return {...raw,plans:raw.plans.map((p)=>{
    let transitionOpacity=1;
    // A change of obstacle topology cannot be safely morphed through the card.
    // Retire the old route before the change, then reveal the new route.
    // All lookahead is sampled by frame number; parallel/random seeking is identical.
    for(let k=Math.floor(f)-7;k<=Math.ceil(f)+7;k++)
      if(k>=OPEN_END && routeJumps(k).has(p.id))transitionOpacity=Math.min(transitionOpacity,seg(Math.abs(f-k),1,7,E_IO));
    return {...p,transitionOpacity};
  })};
};

export const auditLeaderLayout = (f: number) => {
  const c = f < OPEN_END ? SETTLE_CAM : camHub(f), routed = guidePlans(c, f);
  const { z, O } = f < OPEN_END ? { z: 1, O: [W / 2, H / 2] } : zoomAt(f);
  const g = groupAt(f), press = g ? zoomRect(markRect(g.mark, c), z, O) : null;
  const covered = !!g && f >= g.open1 && f < g.end;
  return { ...routed, plans: routed.plans.map((p) => {
    const it = OPENER_LAYOUT.find((q) => q.id === p.id);
    let opacity = 1;
    if (it) {
      const b = boxNow(it, c), lens = cardLensScale(c.s);
      const s = zoomRect({ x: b.x, y: b.y, w: b.w * lens, h: b.h * lens }, z, O);
      const opened = !!g && it.id === g.mark;
      const outside = s.x + s.w < (opened ? -80 : 0) || s.y + s.h < (opened ? -80 : 0) || s.x > W + (opened ? 80 : 0) || s.y > H + (opened ? 80 : 0);
      const hidden = outside || (!opened && ((z > 1.05 && (s.x < 48 || s.y < 48 || s.x + s.w > W - 48 || s.y + s.h > H - 48)) || (!!press && s.x < press.x + press.w && press.x < s.x + s.w && s.y < press.y + press.h && press.y < s.y + s.h)));
      const fade = it.kind === "poi" ? 1 - (poiDim(f)[it.id] ?? 0) : 1 - seg(f, POI_PART - 6, POI_PART + 8);
      const t0 = REVEAL.rooms + it.order * 4;
      opacity = seg(f,t0+4,t0+12) * (hidden ? 0 : 1) * fade * (it.kind === "poi" ? leaderFade(it.id,f) : 1);
    }
    const inFrame = p.anchor.x > 0 && p.anchor.x < W && p.anchor.y > 90 && p.anchor.y < H - 174;
    opacity *= p.transitionOpacity;
    return { ...p, opacity, visible: !covered && opacity > 0.01 && inFrame && p.needed };
  }) };
};

const pinChipStyle: React.CSSProperties = {
  padding: "4px 12px 6px", borderRadius: 10, background: "rgba(251,250,247,0.95)", boxShadow: PAL.shadow,
  fontFamily: SANS, fontWeight: 700, fontSize: OM.font, color: PAL.ink, whiteSpace: "nowrap",
};
const roomChipStyle: React.CSSProperties = {
  padding: "3px 12px 4px", borderRadius: 9, background: "rgba(251,250,247,0.95)", color: PAL.ink,
  fontFamily: SANS, fontWeight: 700, fontSize: 24, whiteSpace: "nowrap", boxShadow: PAL.shadow,
};
const aiBadgeStyle: React.CSSProperties = {
  position: "absolute", left: 7, top: 7, padding: "2px 7px 3px", borderRadius: 5,
  background: "rgba(20,18,20,0.72)", color: "#FBFBF8", fontFamily: SANS, fontWeight: 600, fontSize: 14,
};

// Only the room currently being introduced (or the next one) carries a sharp photo.
// Other cards keep their anchors and readable labels, with a quieter photo preview.
const roomEmphasis = (f: number, id: string) => {
  if (!FOCUS_ROOMS) return 1;
  const rooms = GROUPS.filter((g) => HUB.rooms.some((r) => r.id === g.mark));
  if (!rooms.length) return 1;
  let weight = id === rooms[0].mark ? 1 : 0;
  for (let i = 1; i < rooms.length; i++) {
    const at = Math.min(rooms[i - 1].close1, rooms[i].click);
    const p = seg(f, at - 8, at + 8, E_IO);
    weight = lerp(weight, id === rooms[i].mark ? 1 : 0, p);
  }
  return weight;
};

const PlacedMarks: React.FC<{ f: number; c: Cam; z: number; O: number[]; dim?: Record<string, number>; press?: number; hot?: string; mode?: LabelMode; layer?: "all" | "leaders" | "cards" }> = ({ f, c, z, O, dim = {}, press = 0, hot, mode = "baked", layer = "all" }) => {
  const g = groupAt(f);
  const pressRect = g ? zoomRect(markRect(g.mark, c), z, O) : null;
  const INSET = 48;
  const roomsO = 1 - seg(f, POI_PART - 6, POI_PART + 8);
  const visual = (it: OItem, b: OBox) => {
    const lens = cardLensScale(c.s);
    return { x: b.x, y: b.y, w: b.w * lens, h: b.h * lens, lens };
  };
  const hidden = (it: OItem, b: OBox) => {
    const s = zoomRect(b, z, O);
    // The mark being opened is the source of the expand. Hiding it leaves a hole until the clip arrives.
    if (g && it.id === g.mark) return s.x + s.w < -80 || s.y + s.h < -80 || s.x > W + 80 || s.y > H + 80;
    if (s.x + s.w < 0 || s.y + s.h < 0 || s.x > W || s.y > H) return true;
    if (z > 1.05 && (s.x < INSET || s.y < INSET || s.x + s.w > W - INSET || s.y + s.h > H - INSET)) return true;
    if (pressRect) return s.x < pressRect.x + pressRect.w && pressRect.x < s.x + s.w && s.y < pressRect.y + pressRect.h && pressRect.y < s.y + s.h;
    return false;
  };
  return (
    <>
      {layer !== "cards" && (() => {
        const routed = guidePlans(c, f).plans;
        return <svg width={W} height={H} style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none" }}>
          {routed.map((route) => {
            const it = OPENER_LAYOUT.find((q) => q.id === route.id);
            const b = it ? boxNow(it, c) : null;
            const vis = it && b ? visual(it, b) : null;
            const fade = !it ? 1 : it.kind === "poi" ? 1 - (dim[it.id] ?? 0) : roomsO;
            const t0 = it ? REVEAL.rooms + it.order * 4 : OPEN_END;
            const o = (it ? seg(f, t0 + 4, t0 + 12) : 1) * (it && vis && hidden(it, vis) ? 0 : 1) * fade * (it?.kind === "poi" ? leaderFade(it.id,f) : 1);
            const inF = route.anchor.x > 0 && route.anchor.x < W && route.anchor.y > 90 && route.anchor.y < H - 174;
            const d = route.points.map((p, i) => (i ? "L" : "M") + p.x + " " + p.y).join(" ");
            return <g key={route.id} opacity={o} data-leader={route.id}>
              <g opacity={route.transitionOpacity}>
              {route.needed && route.clear && inF && route.points.length > 1 && <path d={d} fill="none" stroke="rgba(251,250,247,0.90)" strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" />}
              {route.clear && inF && route.points.length > 1 && <path d={d} fill="none" stroke={PAL.ink} strokeWidth={1.6} strokeDasharray={route.kind === "room" ? "5 5" : undefined} strokeLinejoin="round" strokeLinecap="round" />}
              </g>
              {it && it.kind !== "room" && inF && <circle cx={route.anchor.x} cy={route.anchor.y} r={6} fill={ACC} stroke="#FBFAF7" strokeWidth={2} />}
            </g>;
          })}
        </svg>;
      })()}
      {layer !== "leaders" && OPENER_LAYOUT.map((it) => {
        const b = boxNow(it, c);
        const vis = visual(it, b);
        const t0 = REVEAL.rooms + it.order * 4;
        if (f < t0 || hidden(it, vis)) return null;
        const sh = shellStyle(f, [((it.order % 3) - 1) * 110, -120], ((it.order % 2) * 2 - 1) * 6, t0);
        const fade = it.kind === "poi" ? 1 - (dim[it.id] ?? 0) : roomsO;
        const opacity = Number(sh.opacity ?? 1) * fade;
        const hotScale = hot === it.id ? 1 + 0.05 - 0.07 * press : 1;
        const kind = it.kind === "env" ? "env" : it.kind === "poi" ? PO.find((p) => p.id === it.id)!.kind : "";
        const emphasis = roomEmphasis(f, it.id);
        const photo = it.kind === "room" && it.photo ? (
          <div data-harmony-foreground="photo" style={{ position: "relative", width: OM.card.w, height: OM.card.h, borderRadius: 12, overflow: "hidden", background: PAL.card, boxShadow: hot === it.id ? `0 0 0 4px ${ACC}, 0 14px 30px rgba(31,28,23,0.35)` : `0 0 0 4px #FFFFFF, ${PAL.shadow}`, filter: hot === it.id ? "brightness(1.06)" : undefined }}>
            <Img src={staticFile(it.photo)} style={{ width: "100%", height: "100%", objectFit: "cover", opacity: FOCUS_ROOMS ? 0.62 + 0.38 * emphasis : 1, filter: FOCUS_ROOMS ? `blur(${2.8 * (1 - emphasis)}px) saturate(${0.5 + 0.5 * emphasis})` : undefined }} />
            {NOTES && (mode === "scaled-dom" ? <div style={aiBadgeStyle}>AI示意</div> : <div style={{ position: "absolute", left: 7, top: 7 }}><BakedBadge text="AI示意" options={{ fontPx: 14, weight: 600, padX: 7, padT: 2, padB: 3, radius: 5, background: "rgba(20,18,20,0.72)", color: "#FBFBF8" }} shadow={false} /></div>)}
          </div>
        ) : null;
        const roomWords = (
          <span style={roomChipStyle}>
            {ROOM_PREFIX && <span style={{ fontWeight: 500, color: PAL.sub, marginRight: 6, fontSize: 20 }}>{ROOM_PREFIX}</span>}{it.label}
          </span>
        );
        const disc = (
          <div data-harmony-foreground="icon" style={{ width: OM.pin, height: OM.pin, borderRadius: OM.pin / 2, background: it.kind === "env" ? "#3E6B4A" : PAL.card, border: "3px solid #FFFFFF", boxShadow: PAL.shadow, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
            <Icon k={kind} size={OM.icon} color={it.kind === "env" ? "#FFF" : PAL.ink} />
          </div>
        );
        return (
          <div key={it.id} data-map-mark={it.id} data-label-mode={mode} style={{ position: "absolute", left: 0, top: 0, transform: overlayTransform(b.x, b.y), opacity }}>
            <div style={{ transform: sh.transform, transformOrigin: "50% 100%", filter: sh.filter }}>
              <div style={{ transform: hotScale === 1 ? undefined : `scale(${hotScale})`, transformOrigin: it.kind === "room" ? "50% 50%" : "0 50%" }}>
                <div style={{ transform: `scale(${vis.lens})`, transformOrigin: "0 0" }}>
                  {it.kind === "room" ? (
                    <>
                      {photo}
                      {mode === "scaled-dom" && <div style={{ marginTop: 8, width: OM.card.w, textAlign: "center" }}>{roomWords}</div>}
                      {mode === "baked" && <div style={{ marginTop: 8, width: OM.card.w, display: "flex", justifyContent: "center" }}><BakedRoomChip label={it.label} prefix={ROOM_PREFIX} /></div>}
                    </>
                  ) : (
                    <div style={{ height: OM.pin, display: "flex", alignItems: "center" }}>
                      {disc}
                      {mode === "scaled-dom" && <div style={{ marginLeft: 8, ...pinChipStyle }}>{it.label}</div>}
                      {mode === "baked" && <div style={{ marginLeft: 8 }}><BakedPinChip text={it.label} /></div>}
                    </div>
                  )}
                </div>
              </div>
              {mode === "screen-fixed" && (it.kind === "room" ? (
                <>
                  <div style={{ position: "absolute", left: 0, top: 0, transform: overlayTransform((OM.card.w * vis.lens - OM.card.w) / 2, OM.card.h * vis.lens + 8), width: OM.card.w, display: "flex", justifyContent: "center" }}><BakedRoomChip label={it.label} prefix={ROOM_PREFIX} /></div>
                </>
              ) : (
                <div style={{ position: "absolute", left: 0, top: 0, transform: overlayTransform(OM.pin * vis.lens + 8, (OM.pin * vis.lens - OM.pin) / 2), height: OM.pin, display: "flex", alignItems: "center" }}>
                  <BakedPinChip text={it.label} />
                </div>
              ))}
            </div>
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
// --presenter-placeholder (render_episode.py): HeyGen export not generated yet -> frozen first frame + visible tag, no lip motion
export const PRESENTER_PH = (getInputProps() as any).presenterPlaceholder === true;
export const phLoopLen = (fo: { dur?: number }) => Math.max(15, Math.floor((fo.dur ?? 3) * 30) - 1);
export const PlaceholderTag: React.FC<{ x: number; y: number }> = () => null;   // v8c: no on-screen placeholder tag (user 9:15)
const PresenterClip: React.FC<{ L: Line; f: number; from: number }> = ({ L, f, from }) => {
  const fo = presenterFo(L.clip);
  if (PRESENTER_PH && isHG(L.clip)) {   // placeholder: old HeyGen footage (muted), looped when shorter than the segment
    const s0p = L.f0 - HG_PAD, len = phLoopLen(fo);
    return <>{f < s0p ? <Freeze frame={0}><ClipMedia fo={fo} id={L.clip!} local={0} inFrame={0} grade={GRADE_A} /></Freeze>
      : <Sequence from={s0p} layout="none"><Loop durationInFrames={len}><ClipMedia fo={fo} id={L.clip!} local={(f - s0p) % len} inFrame={0} grade={GRADE_A} /></Loop></Sequence>}<PlaceholderTag x={16} y={16} /></>;
  }
  if (!isHG(L.clip)) return <Sequence from={from} layout="none"><ClipMedia fo={fo} id={L.clip ?? "P1"} local={f - from} inFrame={inFor(L, fo)} grade={GRADE_A} /></Sequence>;
  const s0 = L.f0 - HG_PAD;
  if (f < s0) return <Freeze frame={0}><ClipMedia fo={fo} id={L.clip!} local={0} inFrame={0} grade={GRADE_A} /></Freeze>;
  return <Sequence from={s0} layout="none"><ClipMedia fo={fo} id={L.clip!} local={f - s0} inFrame={0} grade={GRADE_A} /></Sequence>;
};
// presenter in-point: varied per line; the sign-off line ends on the clip's last frames (the Muse presenter waves goodbye there)
const inFor = (L: Line, fo: Footage) => { const len = Math.round((fo.dur ?? 10) * 30); const need = L.v1 - L.v0; return Math.max(0, L.end ? len - need - 3 : Math.min(len - need - 4, (LINES.indexOf(L) * 47) % 90)); };

const pathsAt = (f: number): PathDef[] => {
  const paths: PathDef[] = [];
  { const s = focusSpans("metro"); const first = s[0]; if (first && f >= first.a) paths.push({ d: ROUTE as number[][], p: seg(f, first.a + 4, first.a + 4 + TEMPO.move, E_IO), color: ACC, w: 6.5, o: 1, flow: s.some((q) => f >= q.a && f < q.b) ? f : undefined }); }
  for (const p of PO) {
    const dpath = p.kind === "hospital" && p.drive_path ? p.drive_path : p.walk_path;
    if (p.kind === "metro" || !dpath) continue;
    const s = focusSpans(p.id); const sp = s.find((q) => f >= q.a && f < q.b) ?? s.filter((q) => f >= q.b).pop();
    if (!sp) continue;
    const on = f < sp.b;
    paths.push({ d: dpath, p: seg(f, sp.a + 4, sp.a + 4 + TEMPO.move, E_IO), color: p.kind === "hospital" ? "#5A6E86" : PAL.ink, w: 5, o: on ? 0.95 : 0.3, flow: on ? f : undefined });
  }
  return paths;
};

export const probeFrameClean = (f: number) => zoomAt(f).z === 1 && !inCompanionFly(f);

const lensMoves = (abs: number, n: number) => {
  for (let f = abs; f < abs + n; f++) if (camHub(f).s !== camHub(f + 1).s) return true;
  return false;
};
const firstClean = (from: number, to: number, want: number) => {
  let run = 0;
  let runStart = from;
  for (let f = from; f < to; f++) {
    if (probeFrameClean(f)) {
      if (run === 0) runStart = f;
      run++;
      if (run >= want && lensMoves(runStart, want)) return { abs: runStart, n: want };
    } else run = 0;
  }
  return null;
};
const longestClean = (from: number, to: number) => {
  let best: { abs: number; n: number } | null = null;
  let run = 0;
  let runStart = from;
  const keep = () => {
    if (run > 0 && lensMoves(runStart, run) && (!best || run > best.n)) best = { abs: runStart, n: run };
  };
  for (let f = from; f < to; f++) {
    if (probeFrameClean(f)) {
      if (run === 0) runStart = f;
      run++;
    } else {
      keep();
      run = 0;
    }
  }
  keep();
  return best;
};
const pickLabelProbe = () => {
  const want = 48;
  for (const seg of MOTION_SEGS) {
    const hit = firstClean(Math.max(seg.f0, OPEN_END), seg.f1, want);
    if (hit) return hit;
  }
  const limit = MOTION_SEGS.length ? MOTION_SEGS[MOTION_SEGS.length - 1].f1 + 240 : OPEN_END + 400;
  return firstClean(OPEN_END, limit, want) ?? longestClean(OPEN_END, limit) ?? { abs: OPEN_END, n: 0 };
};
const pickedProbe = pickLabelProbe();
const probeN = Math.min(pickedProbe.n, 48);
const probeOk = (pred: (f: number) => boolean) => {
  if (probeN <= 0) return false;
  for (let i = 0; i < probeN; i++) if (!pred(pickedProbe.abs + i)) return false;
  return true;
};
export const LABEL_PROBE = {
  abs: pickedProbe.abs,
  n: probeN,
  end: pickedProbe.abs + probeN,
  scaleChanges: lensMoves(pickedProbe.abs, probeN),
  zoomIs1: probeOk((f) => zoomAt(f).z === 1),
  avoidsCompanionFly: probeOk((f) => !inCompanionFly(f)),
};

const CompanionTitle: React.FC<{ f: number; open1: number; kicker: string; title: string }> = ({ f, open1, kicker, title }) => {
  const landed = companionPhase(f, open1, kicker, title) === "static";
  return (
    <div data-harmony-foreground="title" style={{ position: "absolute", left: 60, top: 96, display: "flex", alignItems: "center", gap: 12, fontFamily: SANS, color: "#FFF", textShadow: "0 1px 6px rgba(0,0,0,0.5)" }}>
      <div style={{ width: 28, height: 3, borderRadius: 2, background: PAL.gold, ...shellStyle(f, [-120, 0], 0, open1) }} />
      {landed ? (
        <>
          {kicker && <span style={{ fontWeight: 600, fontSize: 20, letterSpacing: 1, opacity: 0.85 }}>{kicker}</span>}
          <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 40 }}>{title}</span>
        </>
      ) : (
        <>
          {kicker && <FlyText seed={500} start={open1 + 2} step={1} style={{ fontWeight: 600, fontSize: 20, letterSpacing: 1, opacity: 0.85 }} runs={[{ s: kicker }]} />}
          <FlyText seed={520} start={open1 + 6} step={2} style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 40 }} runs={[{ s: title }]} />
        </>
      )}
    </div>
  );
};

export const MapHubKoubo: React.FC = () => {
  const f = useCurrentFrame();
  const L = lineAt(f);
  const c = camHub(f);
  const g = groupAt(f);
  const { z, O } = zoomAt(f);
  const cur = cursorAt(f);
  const hub = f >= OPEN_END - 2;

  // paths on the plane: metro route (opener's snapped polyline) + walking routes of focused POIs
  const paths = pathsAt(f);

  // overlays
  const showA = L.layout === "A" && f >= aStart(L);
  let rect: Rect | null = null, open = 0;
  if (g) {
    if (f < g.end) { const p = seg(f, OPEN_A(g.click), g.open1, E_IO); rect = lerpRect(zoomRect(markRect(g.mark, camHub(g.click)), z, O), FULL, p); open = p; }
    else { const p = seg(f, g.end, g.close1, E_IO); rect = lerpRect(FULL, zoomRect(markRect(g.mark, c), z, O), p); open = 1 - p; }
  }
  const gLine = g ? (g.lines.filter((l) => l.v0 <= f || l === g.lines[0]).pop() ?? g.lines[0]) : undefined;
  const gStart = (l: Line) => (g && l === g.lines[0] ? g.click : l.v0);
  const endP = seg(f, END0, END0 + TEMPO.trans, E_IO);
  const dark = Math.max(showA ? 1 : open, endP);
  const dim = poiDim(f);

  // caption chunk
  const capLine = LINES.find((l) => f >= l.f0 && f < Math.min(l.f1 + (l.hold_f ? 0 : 8), l.v1));   // hold lines: caption ends with the last word (the hold shows other footage)   // never carry a caption across a cut into the next visual
  const cap = capLine ? capLine.caps.filter((q) => q.f0 <= f).pop() ?? capLine.caps[0] : undefined;

  const credit = f < 130 ? "房源照片为AI示意或图库示意" : showA ? (isHG(L.clip) ? "AI数字人 · AI合成声音" : "主持人画面为AI生成") : open > 0.5 ? "AI生成示意 非实拍" : EP.mapBase.credit;

  return (
    <AbsoluteFill style={{ background: PAL.land, overflow: "hidden" }}>
      <Audio src={staticFile("episode/mix.wav")} />
      {/* ===== hub map world (zoom layer: plane + marks + cursor share one transform so the click point never drifts) ===== */}
      {hub && !(g && f >= g.open1 && f < g.end) && (
        <AbsoluteFill style={{ transform: `scale(${z})`, transformOrigin: `${O[0]}px ${O[1]}px`, filter: CLEAN_END && f >= END0 ? `blur(${10 * endP}px)` : undefined }}>
          <HubPlane c={c} paths={paths} aoiP={seg(f, OPEN_END - 4, OPEN_END + 30, E_IO)} poiAoi={POI_AOI.map((a) => ({ pts: a.pts, p: seg(f, a.f0 - 6, a.f0 + 24, E_IO) }))} />
          <AbsoluteFill style={{ background: `linear-gradient(180deg, ${PAL.land}C8 0%, ${PAL.land}00 13%, ${PAL.land}00 70%, ${PAL.land}C0 96%)` }} />
          {f >= OPEN_END && <PlacedMarks f={f} c={c} z={z} O={O} dim={dim} layer="leaders" />}
          {f >= OPEN_END && <Marks f={f} c={c} z={z} O={O} hot={cur.hot} press={cur.ev?.click ? seg(f, cur.ev.f - 2, cur.ev.f + 1) * (1 - seg(f, cur.ev.f + 6, cur.ev.f + 10)) : 0} />}
          {f >= OPEN_END && <PlacedMarks f={f} c={c} z={z} O={O} dim={dim} layer="cards" hot={cur.hot} press={cur.ev?.click ? seg(f, cur.ev.f - 2, cur.ev.f + 1) * (1 - seg(f, cur.ev.f + 6, cur.ev.f + 10)) : 0} />}
        </AbsoluteFill>
      )}

      {/* ===== opener through frame 239. Frame 240 is the hub at the same settled camera, one mark, no crossfade. ===== */}
      {f < OPEN_END && (
        <Sequence durationInFrames={OPEN_END}>
          <AbsoluteFill><Opener theme="light" map="flovaSat3Db" strip={false} chrome={false} drawRoute={false} metroMark={false} /></AbsoluteFill>
        </Sequence>
      )}
      {f >= REVEAL.rooms && f < OPEN_END && <PlacedMarks f={f} c={SETTLE_CAM} z={1} O={[W / 2, H / 2]} />}

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
        const title = clipTitleFor(g.mark, gLine.clip);
        const kicker = kickerFor(g.mark);
        const tag = !NOTES ? undefined : (HUB.clipTags as Record<string, string> | undefined)?.[gLine.clip!];
        return (
          <div style={{ position: "absolute", left: rect.x, top: rect.y, width: rect.w, height: rect.h, borderRadius: lerp(Math.min(rect.h / 2, 14 / Math.min(sx, sy)), 0, open) * Math.min(sx, sy), overflow: "hidden", boxShadow: open < 0.98 ? "0 20px 50px rgba(0,0,0,0.35)" : undefined }}>
            <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${sx}, ${sy})`, transformOrigin: "0 0" }}>
              {g.lines.map((l) => (l === gLine ? (
                <Sequence key={l.id} from={gStart(l)} layout="none">
                  <AbsoluteFill><ClipMedia fo={fo} id={l.clip!} local={local} grade="saturate(0.9)" sceneRole={full ? "world" : "foreground"} /></AbsoluteFill>
                </Sequence>
              ) : null))}
              {full && <ScanAnnotate fo={fo} ann={AN[gLine.clip!]} inFrame={12} reserved={g.lines.filter((l) => !!l.pip).map((l) => PIP_EXCEPT[l.id] ? { x: PIP_EXCEPT[l.id].x, y: PIP_EXCEPT[l.id].y, w: PIP_R.w, h: PIP_R.h } : PIP_R)} local={f - Math.max(gStart(gLine), g.open1)} mediaOffset={Math.max(gStart(gLine), g.open1) - gStart(gLine)} outAt={g.end - Math.max(gStart(gLine), g.open1) - 7} />}
              {full && tag && (
                <div style={{ position: "absolute", left: 100, top: 150, padding: "3px 10px 4px", borderRadius: 6, background: "rgba(20,18,16,0.55)", color: "#FFF", fontFamily: SANS, fontWeight: 600, fontSize: 17, letterSpacing: 1, opacity: seg(f, g.open1 + 8, g.open1 + 14) }}>{tag}</div>
              )}
            </div>
            {full && <CompanionTitle f={f} open1={g.open1} kicker={kicker} title={title} />}
          </div>
        );
      })()}

      {/* ===== presenter PiP on any line with `pip` (HeyGen segment id): small card over map / B-roll; bottom-right (or bottom-left) above the caption ===== */}
      {L.pip && (() => {
        const PL = { ...L, clip: L.pip } as Line;
        // v8 rule (小窗口在不遮挡关键信息时不要挪动位置): one fixed rect = map PiP (PIP_R); pipPos is ignored unless the line is in PIP_EXCEPT
        const exc = PIP_EXCEPT[L.id];
        const w = PIP_R.w, h = PIP_R.h, left = exc ? exc.x : PIP_R.x, pipTop = exc ? exc.y : PIP_R.y;
        const li = LINES.indexOf(L), prevPip = li > 0 && !!LINES[li - 1].pip, nextPip = li + 1 < LINES.length && !!LINES[li + 1].pip;
        const o = (prevPip ? 1 : seg(f, L.f0 - HG_PAD - 6, L.f0 - HG_PAD + 4)) * (nextPip ? 1 : 1 - seg(f, L.v1 - 6, L.v1));   // consecutive PiP lines: one card, no dip
        return (
          <>
            <div style={{ position: "absolute", left, top: pipTop, width: w, height: h, opacity: o, borderRadius: 14, overflow: "hidden", border: "2px solid #FFFFFF", boxShadow: "0 12px 30px rgba(31,28,23,0.35)" }}>
              <div style={{ width: W, height: H, transform: `scale(${w / W})`, transformOrigin: "0 0" }}><PresenterClip L={PL} f={f} from={L.v0} /></div>
            </div>
            {NOTES && <AvatarBadge x={left + 8} y={pipTop - 34} size={14} o={o} />}
          </>
        );
      })()}
      {POI_AOI.filter((a) => a.credit && f >= a.f0 - 6).slice(0, 1).map((a) => (
        <div key={a.id} style={{ position: "absolute", left: 60, bottom: 96, fontFamily: SANS, fontSize: 14, color: "rgba(60,55,48,0.75)", opacity: hub ? 1 : 0 }}>{a.credit}</div>
      ))}
      {/* ===== cursor + click ripple: same zoom transform as the map, drawn ABOVE the opening clip so press + ripple stay visible ===== */}
      {hub && (
        <AbsoluteFill style={{ transform: `scale(${z})`, transformOrigin: `${O[0]}px ${O[1]}px`, pointerEvents: "none" }}>
          {/* single plain pointer (no name tag) */}
                    {f >= (LINES.find((l) => l.fx === "duet")?.v0 ?? 1e9) && !showA && L.layout !== "END" && (() => {
            const duet = LINES.find((l) => l.fx === "duet")!;
            const lit = seg(f, duet.v0 + 40, duet.v0 + 40 + TEMPO.trans, E_IO);
            const appear = seg(f, duet.v0 + 10, duet.v0 + 10 + TEMPO.move, E_OUT);
            const press = cur.ev?.click ? seg(f, cur.ev.f - 2, cur.ev.f + 1) * (1 - seg(f, cur.ev.f + 6, cur.ev.f + 10)) : 0;
            // drawn point (pre-clamp): entrance glide or live target, in the map layer's pre-zoom coordinates
            const px0 = f < duet.v0 + 10 + TEMPO.move ? lerp(1500, cur.x, appear) : cur.x, py0 = f < duet.v0 + 10 + TEMPO.move ? lerp(1000, cur.y, appear) : cur.y;
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
            {(EP as any).sampleData === true && <div style={{ fontFamily: SANS, fontStyle: "normal", fontWeight: 600, fontSize: 20, color: "#FFF", opacity: 0.8, marginTop: 10, letterSpacing: 2 }}>{EP.sampleTag}</div>}
          </div>
        );
      })()}
      {showA && L.end && f >= L.caps[L.caps.length - 1].f0 && (
        <div style={{ position: "absolute", left: 100, top: 400, color: "#FFF", fontFamily: TITLE, fontWeight: 700, fontSize: 72, textShadow: "0 2px 12px rgba(0,0,0,0.45)" }}>
          <FlyText seed={700} start={L.caps[L.caps.length - 1].f0} step={2} runs={[{ s: EP.channel }]} />
          <div style={{ fontFamily: NUM, fontStyle: "italic", fontSize: 34, opacity: 0.85, marginTop: 4 }}><FlyText seed={740} start={L.caps[L.caps.length - 1].f0 + 10} step={1} runs={[{ s: EP.episodeTag }]} /></div>
          {NOTES && isHG(L.clip) && <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 20, opacity: seg(f, L.caps[L.caps.length - 1].f0 + 14, L.caps[L.caps.length - 1].f0 + 22), marginTop: 14, letterSpacing: 1, textShadow: "none" }}>出镜为 AI数字人 · 旁白为 AI合成声音{(EP as any).sampleData === true ? " · " + EP.sampleTag : ""}</div>}
        </div>
      )}

      {/* footnote (e.g. school line) */}
      {NOTES && L.note && !g && <div style={{ position: "absolute", left: 60, bottom: 196, fontFamily: SANS, fontWeight: 500, fontSize: 16, color: PAL.sub, background: "rgba(251,250,247,0.85)", padding: "3px 10px 4px", borderRadius: 6 }}>{L.note}</div>}


      {/* ===== END: summary panel (shotcraft list-reveal rows + domino-cascade brand row) + avatar small PiP ===== */}
      {f >= END0 && (() => {
        const t0 = END0;
        const rows: [string, string][] = [
          ["户型", `${CHOSEN.layout} · ${CHOSEN.area}㎡ · ${CHOSEN.rent}元/月`],
          ["室内", (EP as any).endCard?.interior ?? "整面落地窗 · 人字拼木地板 · 干湿分离"],
          ...PO.filter((p) => ["metro", "school1", "market", "mall", "hospital", "park"].includes(p.id)).map((p) => [({ metro: "地铁", school: "学校", market: "超市", mall: "商场", hotel: "酒店", hospital: "医院", park: "公园" } as Record<string, string>)[p.kind] ?? "", `${p.label} · ${distText(p)}`] as [string, string]),
        ];
        const EL = LINES.find((l) => l.layout === "END" && l.v0 <= f && f < l.v1) ?? LINES.filter((l) => l.layout === "END").pop()!;
        const lastL = LINES[LINES.length - 1];
        if (CLEAN_END) {
          const promo = (EP as any).endCard?.promo as string[] | undefined;
          return (
            <>
              <AbsoluteFill style={{ background: `rgba(24,21,18,${0.88 * endP})` }} />
              <div data-harmony-foreground="title" style={{ position: "absolute", left: 72, top: 96, color: PAL.card, opacity: endP, transform: `translateY(${lerp(16, 0, endP)}px)` }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 16, fontFamily: SANS, fontWeight: 600, fontSize: 24, color: PAL.gold }}>
                  <span>{EP.channel}</span><span style={{ fontFamily: NUM, fontStyle: "italic", fontSize: 22 }}>{EP.episodeTag}</span>
                </div>
                <div style={{ marginTop: 14, fontFamily: TITLE, fontWeight: 700, fontSize: 54, lineHeight: 1.2 }}>{CHOSEN.community}</div>
              </div>
              <div style={{ position: "absolute", left: 72, top: 320, width: 930, fontFamily: SANS, color: PAL.card }}>
                {rows.map(([k, v], i) => {
                  const a = t0 + 14 + i * TEMPO.stagger;
                  const q = seg(f, a, a + 12, E_OUT);
                  return (
                    <div key={k + i} style={{ display: "grid", gridTemplateColumns: "60px minmax(0, 1fr)", alignItems: "baseline", columnGap: 20, padding: "14px 0", borderBottom: "1px solid rgba(251,250,247,0.14)", opacity: q, transform: `translateY(${lerp(14, 0, q)}px)` }}>
                      <span style={{ fontWeight: 600, fontSize: 20, color: PAL.gold }}>{k}</span>
                      <span style={{ fontWeight: 600, fontSize: k === "室内" ? 26 : 32, lineHeight: 1.35 }}>{v}</span>
                    </div>
                  );
                })}
              </div>
              {promo && <div style={{ position: "absolute", left: 72, top: 660, display: "flex", alignItems: "baseline", gap: 16, fontFamily: SANS, opacity: seg(f, t0 + 36, t0 + 48, E_OUT) }}>
                <span style={{ color: PAL.gold, fontSize: 20, fontWeight: 700 }}>{promo[0]}</span>
                <span style={{ color: PAL.card, fontSize: 24, fontWeight: 500 }}>{promo[1]}<span style={{ color: PAL.gold, fontWeight: 700 }}>{promo[2]}</span>{promo[3]}</span>
              </div>}
              <div style={{ position: "absolute", left: 72, top: 724, opacity: seg(f, t0 + 50, t0 + 62, E_OUT) }}>
                <div style={{ fontFamily: SANS, fontSize: 16, fontWeight: 500, color: "rgba(251,250,247,0.70)", marginBottom: 12 }}>{BRANDS.rowLabel}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
                  {BRANDS.row.map((b) => <Mono key={b.name} file={b.file} ar={b.ar} h={b.h * 1.3} color="#FBFAF7" />)}
                </div>
              </div>
              <div style={{ position: "absolute", right: 72, top: 390, width: 300, height: 220, borderRadius: 14, overflow: "hidden", border: "1px solid rgba(251,250,247,0.65)", boxShadow: PAL.shadow, opacity: endP }}>
                <div style={{ width: W, height: H, transform: `scale(${300 / W})`, transformOrigin: "0 0" }}><PresenterClip L={EL} f={f} from={EL.v0} /></div>
              </div>
              {NOTES && <div style={{ position: "absolute", left: 72, top: 814, color: PAL.card, fontFamily: SANS, fontSize: 16, opacity: endP }}>出镜为 AI数字人 · 旁白为 AI合成声音{(EP as any).sampleData === true ? " · 房源为" + EP.sampleTag : ""}</div>}
            </>
          );
        }
        return (
          <>
            {(EP as any).endCard?.dim === "top" ? <AbsoluteFill style={{ background: `linear-gradient(180deg, rgba(24,21,18,${0.86 * endP}) 0%, rgba(24,21,18,${0.8 * endP}) 44%, rgba(24,21,18,${0.12 * endP}) 58%, rgba(24,21,18,0) 100%)` }} /> : <AbsoluteFill style={{ background: `rgba(24,21,18,${0.82 * endP})` }} />}
            <div style={{ position: "absolute", left: 70, top: 110, width: 900, fontFamily: SANS, color: "#FFF", opacity: endP, transform: `translateY(${lerp(30, 0, endP)}px)` }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
                <FlyText seed={800} start={t0 + 4} step={2} style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 64 }} runs={[{ s: EP.channel }]} />
                <span style={{ fontFamily: NUM, fontStyle: "italic", fontSize: 30, opacity: 0.8 }}>{EP.episodeTag}</span>
              </div>
              <div style={{ marginTop: 8, fontSize: 30, fontWeight: 700, color: PAL.gold }}>{CHOSEN.community}{NOTES && (EP as any).sampleData === true && <span style={{ marginLeft: 14, fontSize: 18, fontWeight: 600, padding: "2px 8px 3px", border: "1.5px solid #FFF", borderRadius: 6, color: "#FFF" }}>{EP.sampleTag}</span>}</div>
              <div style={{ marginTop: 22 }}>
                {rows.map(([k, v], i) => {
                  const a = t0 + 14 + i * TEMPO.stagger; const q = seg(f, a, a + TEMPO.enter, E_OUT);
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
                  const a = t0 + 14 + rows.length * TEMPO.stagger + i * TEMPO.stagger; const q = seg(f, a, a + 8, E_OUT);
                  return <div key={b.name} style={{ opacity: q, transform: `translateY(${lerp(-26, 0, q)}px) rotate(${lerp(-8, 0, q)}deg)` }}><Mono file={b.file} ar={b.ar} h={b.h * 1.6} color="#FFFFFF" /></div>;
                })}
              </div>
              {NOTES && <div style={{ marginTop: 26, fontSize: 17, fontWeight: 600, opacity: seg(f, lastL.f0, lastL.f0 + 8) * 0.9 }}>出镜为 AI数字人 · 旁白为 AI合成声音{(EP as any).sampleData === true ? " · 房源为" + EP.sampleTag : ""}</div>}
            </div>
            {/* host PiP moved to the upper right so it never covers the in-panel brand row or the bottom brand strip */}
            <div style={{ position: "absolute", right: 64, top: 96, width: 300, height: 220, borderRadius: 16, overflow: "hidden", border: "3px solid #FFFFFF", boxShadow: "0 14px 34px rgba(0,0,0,0.45)", opacity: endP, transform: `scale(${lerp(0.85, 1, endP)})`, transformOrigin: "100% 0%" }}>
              <div style={{ width: W, height: H, transform: `scale(${300 / W})`, transformOrigin: "0 0" }}><PresenterClip L={EL} f={f} from={EL.v0} /></div>
            </div>
            {NOTES && (<AvatarBadge x={W - 64 - 300 + 8} y={96 + 220 + 10} size={15} o={endP} />)}
          </>
        );
      })()}

      {/* END promo 花字 (v8g): dark plum lettering with white outline (reads on the light map), 一手房源 chip, red emphasis + ep01 MarkerUnderline (red) drawn on after the pop-in */}
      {!CLEAN_END && f >= END0 + 18 && (EP as any).endCard?.promo && (() => {
        const p = seg(f, END0 + 18, END0 + 18 + TEMPO.trans); const sc = p <= 0 ? 0 : lerp(0.2, 1, p) + 0.22 * Math.sin(Math.PI * p) * (1 - 0.3 * p);
        const [chip, pre, hi, post] = (EP as any).endCard.promo as string[];
        const big = { fontFamily: TITLE, fontWeight: 700, fontSize: 70, lineHeight: 1.1, WebkitTextStroke: "12px #FFFFFF", paintOrder: "stroke fill" as const, textShadow: "0 6px 18px rgba(30,12,50,0.35)" };
        return (
          <div style={{ position: "absolute", right: 70, top: 630, transform: `rotate(-4deg) scale(${sc})`, transformOrigin: "80% 50%", opacity: Math.min(1, sc * 2), textAlign: "right" }}>
            <div style={{ display: "inline-block", background: "#7B2FF7", padding: "6px 22px 10px", borderRadius: 14, border: "4px solid #2A0F4F", boxShadow: "6px 6px 0 #2A0F4F" }}>
              <span style={{ fontFamily: TITLE, fontWeight: 700, fontSize: 44, color: "#FFFFFF", WebkitTextStroke: "6px #2A0F4F", paintOrder: "stroke fill" }}>{chip}</span>
            </div>
            <div style={{ marginTop: 8, whiteSpace: "nowrap" }}>
              <span style={{ ...big, color: "#2A0F4F" }}>{pre}</span>
              <span style={{ position: "relative", display: "inline-block" }}>
                <span style={{ ...big, color: "#E8202A", position: "relative", zIndex: 1 }}>{hi}</span>
                <MarkerUnderline len={Array.from(hi).length * 70 * 0.95} local={f} start={END0 + 34} seed={31} color="#E8202A" style={{ left: 0, bottom: -46, zIndex: -1 }} />
              </span>
              <span style={{ ...big, color: "#2A0F4F" }}>{post}</span>
            </div>
          </div>
        );
      })()}
      {/* captions (non-END) */}
      {SPACE3D && <Space3DClips spec={SPACE3D} f={f} />}
      {/* Caption rule (CONVENTIONS-shared.md): one fixed centred spot, bottom 118. Exceptions:
   OPEN_TITLE (main f150-OPEN_END): centred box collides with title-block price row "3000?/?" -> right-aligned, size 40. */}
{cap && <Caption text={cap.text} right={f < OPEN_END && f > 150} size={f < OPEN_END && f > 150 ? 40 : 46} />}
      {/* END caption: left-aligned inside the summary column; box bottom 36px above the brand strip, clear of the upper-right PiP */}
      {false /* END caption now centred via main Caption */ && cap && f >= END0 && (
        <div style={{ position: "absolute", left: 70, width: 900, bottom: 104, textAlign: "left" }}>
          <span style={{ display: "inline-block", padding: "7px 18px 10px", borderRadius: 10, background: "rgba(18,16,14,0.55)", color: "#FFFFFF", fontFamily: SANS, fontWeight: 700, fontSize: 42, lineHeight: 1.25, letterSpacing: 1 }}>{cap!.text}</span>
        </div>
      )}

      {/* chrome: sample-data tag + context credit */}
      <div style={{ position: "absolute", left: 60, top: 54, display: NOTES ? "flex" : "none", gap: 12, alignItems: "center", fontFamily: SANS, color: dark > 0.5 ? "#FFF" : PAL.ink, textShadow: dark > 0.5 ? "0 1px 4px rgba(0,0,0,0.5)" : undefined }}>
        {(EP as any).sampleData === true && <div style={{ padding: "3px 10px 4px", borderRadius: 6, border: `1.5px solid ${dark > 0.5 ? "#FFF" : PAL.ink}`, opacity: 0.85, fontWeight: 700, fontSize: 15 }}>{EP.sampleTag}</div>}
        <div style={{ fontWeight: 500, fontSize: 14, opacity: 0.85 }}>{credit}</div>
      </div>

      <BrandStrip dark={dark} />
    </AbsoluteFill>
  );
};

/** Same camera as the episode, three label drawings, no footage. */
export const LabelJitterProbe: React.FC<{ mode?: LabelMode; startFrame?: number }> = ({ mode = "baked", startFrame = LABEL_PROBE.abs }) => {
  const f = startFrame + useCurrentFrame();
  const c = camHub(f);
  return (
    <AbsoluteFill style={{ background: PAL.land, overflow: "hidden" }}>
      <HubPlane c={c} paths={pathsAt(f)} aoiP={seg(f, OPEN_END - 4, OPEN_END + 30, E_IO)} poiAoi={POI_AOI.map((a) => ({ pts: a.pts, p: seg(f, a.f0 - 6, a.f0 + 24, E_IO) }))} />
      <AbsoluteFill style={{ background: `linear-gradient(180deg, ${PAL.land}C8 0%, ${PAL.land}00 13%, ${PAL.land}00 70%, ${PAL.land}C0 96%)` }} />
      <PlacedMarks f={f} c={c} z={1} O={[W / 2, H / 2]} mode={mode} />
    </AbsoluteFill>
  );
};
