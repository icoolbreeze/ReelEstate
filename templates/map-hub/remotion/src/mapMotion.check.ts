// Frame-pure gates for the hub camera and the mark handoff.
// Run from the episode work tree: npx --yes tsx src/mapMotion.check.ts
import HUB from "./episode/hub.json";
import POIS from "./episode/pois.json";
import TL from "./episode/timeline.json";
import { auditLayout, camHub, MOTION_SEGS } from "./MapHubKoubo";
import { projectPoint, velocityGlitch, type Cam } from "./mapMotion";

const OPEN_END = TL.opener as number;
const HOFF = { x: 82, y: -58 };
const LST = (POIS as { listing: { xy: number[] } }).listing.xy;
const pois = (POIS as { pois: { id: string; xy: number[] }[] }).pois;
const env = (HUB as { env: { id: string; dxy: number[] } }).env;

const geo = (kind: string, id: string, c: Cam) => {
  if (kind === "poi") {
    const p = pois.find((q) => q.id === id);
    return projectPoint(c, p ? p.xy[0] : LST[0], p ? p.xy[1] : LST[1]);
  }
  if (kind === "env") return projectPoint(c, LST[0] + env.dxy[0], LST[1] + env.dxy[1]);
  return projectPoint(c, LST[0], LST[1]);
};

const screen = (f: number) => projectPoint(camHub(f), LST[0], LST[1]);
const step = (f: number) => {
  const a = screen(f);
  const b = screen(f + 1);
  return Math.hypot(b.x - a.x, b.y - a.y);
};

const fails: string[] = [];
const before = auditLayout(OPEN_END - 1);
const after = auditLayout(OPEN_END);
let handoffMax = 0;
for (const m of before.marks) {
  const n = after.marks.find((q) => q.id === m.id);
  if (!n) { fails.push("missing " + m.id); continue; }
  for (const k of ["x", "y", "w", "h", "lens", "ax", "ay"] as const) handoffMax = Math.max(handoffMax, Math.abs(m[k] - n[k]));
}
if (handoffMax >= 0.5) fails.push("handoff " + handoffMax);
const camKeys = ["s", "fx", "fy", "tilt", "P"] as const;
let camHandoff = 0;
for (const k of camKeys) camHandoff = Math.max(camHandoff, Math.abs(before.cam[k] - after.cam[k]));
if (camHandoff > 1e-6) fails.push("cam handoff " + camHandoff);

let anchorError = 0;
for (const f of [OPEN_END - 1, OPEN_END, OPEN_END + 20, 400, 900, 1600, 2000]) {
  const a = auditLayout(f);
  const draw = f < OPEN_END ? before.cam : a.cam;
  for (const m of a.marks) {
    const g = geo(m.kind, m.id, draw);
    anchorError = Math.max(anchorError, Math.hypot(m.gx - g.x, m.gy - g.y));
    const ex = g.x + (m.kind === "room" ? HOFF.x : 0);
    const ey = g.y + (m.kind === "room" ? HOFF.y : 0);
    anchorError = Math.max(anchorError, Math.hypot(m.ax - ex, m.ay - ey));
  }
}
if (anchorError >= 1) fails.push("anchor " + anchorError);

const again = JSON.stringify(auditLayout(OPEN_END + 17));
if (again !== JSON.stringify(auditLayout(OPEN_END + 17)) || JSON.stringify(camHub(880)) !== JSON.stringify(camHub(880))) fails.push("nondeterministic");

let glitch = false;
const mids: number[] = [];
for (const s of MOTION_SEGS) {
  const steps: number[] = [];
  for (let f = s.f0 + 8; f <= s.f1 - 8; f++) steps.push(step(f));
  if (steps.length >= 4) {
    mids.push(...steps);
    if (velocityGlitch(steps)) glitch = true;
  }
  if (step(s.f0) > 4 || step(s.f1 - 1) > 4) fails.push("boundary " + s.f0 + " " + step(s.f0) + " " + step(s.f1 - 1));
}
if (glitch) fails.push("stall-jump");
const lastSeg = MOTION_SEGS[MOTION_SEGS.length - 1];
const tailStep = step(lastSeg.f1 + 80);
if (!(tailStep > 0.05)) fails.push("end hold frozen " + tailStep);

let fractional = false;
for (let f = OPEN_END + 1; f <= OPEN_END + 30; f++) {
  if (auditLayout(f).marks.some((m) => m.x % 1 !== 0 || m.y % 1 !== 0)) fractional = true;
}
if (!fractional) fails.push("positions look rounded");

const report = {
  ok: fails.length === 0,
  fails,
  handoffMax,
  camHandoff,
  anchorError,
  segs: MOTION_SEGS.map((s) => ({ f0: s.f0, f1: s.f1, next: s.next })),
  midStepMax: mids.reduce((a, b) => Math.max(a, b), 0),
  tailStep,
  endCam: camHub(2100),
  endCamLater: camHub(2300),
  sample: { f: OPEN_END + 12, cam: camHub(OPEN_END + 12), mark: auditLayout(OPEN_END + 12).marks[0] },
};
console.log(JSON.stringify(report));
const proc = (globalThis as { process?: { exit: (code: number) => never } }).process;
if (!report.ok) throw new Error(fails.join("; "));
proc?.exit(0);
