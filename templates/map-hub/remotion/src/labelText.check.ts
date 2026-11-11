// Label drawing contract for the camera-move comparison.
// Run from the episode work tree: npx --yes tsx src/labelText.check.ts
import { camHub, companionFlyEnd, companionPhase, LABEL_PROBE, labelTextPlan, probeFrameClean } from "./MapHubKoubo";

const fails: string[] = [];
if (LABEL_PROBE.n < 24) fails.push("probe n " + LABEL_PROBE.n);
if (!LABEL_PROBE.zoomIs1) fails.push("zoom flag");
if (!LABEL_PROBE.avoidsCompanionFly) fails.push("fly flag");
if (!LABEL_PROBE.scaleChanges) fails.push("scale flag");
if (LABEL_PROBE.end !== LABEL_PROBE.abs + LABEL_PROBE.n) fails.push("end");

for (let i = 0; i < LABEL_PROBE.n; i++) {
  const f = LABEL_PROBE.abs + i;
  if (!probeFrameClean(f)) fails.push("dirty " + f);
}
let changed = false;
for (let i = 0; i < LABEL_PROBE.n; i++) {
  const f = LABEL_PROBE.abs + i;
  if (camHub(f).s !== camHub(f + 1).s) changed = true;
}
if (!changed) fails.push("lens still");

const room = labelTextPlan("screen-fixed", "room");
const pin = labelTextPlan("screen-fixed", "poi");
const env = labelTextPlan("screen-fixed", "env");
if (room.inLensScale || room.motion !== "translate" || room.fontPx !== 24 || room.liveDomText !== false || room.rasterScale !== 3) fails.push("screen room");
if (pin.inLensScale || pin.fontPx !== 26 || env.fontPx !== 26 || env.inLensScale) fails.push("screen pin");

const baked = labelTextPlan("baked", "poi");
if (!baked.inLensScale || baked.rasterScale !== 3 || baked.liveDomText !== false || baked.motion !== "image-scale") fails.push("baked");
const dom = labelTextPlan("scaled-dom", "room");
if (!dom.inLensScale || dom.motion !== "lens-scale" || dom.liveDomText !== true) fails.push("dom");

const open1 = 1000;
const kick = "周边配套";
const title = "双桥路";
const end = companionFlyEnd(open1, kick, title);
if (!(end > open1)) fails.push("fly end");
if (companionPhase(open1, open1, kick, title) !== "fly") fails.push("phase start");
if (companionPhase(end, open1, kick, title) !== "fly") fails.push("phase land");
if (companionPhase(end + 1, open1, kick, title) !== "static") fails.push("phase static");
if (companionPhase(open1 - 1, open1, kick, title) !== "off") fails.push("phase off");

const report = { ok: fails.length === 0, fails, probe: LABEL_PROBE };
console.log(JSON.stringify(report));
const proc = (globalThis as { process?: { exit: (code: number) => never } }).process;
if (!report.ok) throw new Error(fails.join("; "));
proc?.exit(0);
